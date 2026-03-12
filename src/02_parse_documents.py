# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Parse Documents
# MAGIC
# MAGIC Processes documents in batches using `ai_parse_document`.
# MAGIC Includes retry logic with exponential backoff for transient failures.

# COMMAND ----------

# MAGIC %pip install pyyaml
# MAGIC %restart_python

# COMMAND ----------

import os
import sys
import time
import math
import traceback

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load configuration

# COMMAND ----------

config_path = dbutils.widgets.get("config_path")

sys.path.insert(0, os.path.dirname(os.path.dirname(config_path)))
from src.utils.config import load_config

config = load_config(config_path)

run_id = dbutils.jobs.taskValues.get(taskKey="ingest_documents", key="run_id")
raw_count = dbutils.jobs.taskValues.get(taskKey="ingest_documents", key="raw_count")

print(f"Pipeline run ID: {run_id}")
print(f"Documents to parse: {raw_count}")

if raw_count == 0:
    print("All documents already parsed. Nothing to do.")
    dbutils.jobs.taskValues.set(key="run_id", value=run_id)
    dbutils.jobs.taskValues.set(key="total_parsed", value=0)
    dbutils.notebook.exit("skip")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Assign batch IDs

# COMMAND ----------

batch_size = config.processing.batch_size
num_batches = max(1, math.ceil(raw_count / batch_size))

raw_table = config.fqn(config.storage.tables.raw_documents)

# Round-robin assignment by file size rank so each batch gets a mix of
# large and small documents, distributing load evenly across batches.
spark.sql(f"""
CREATE OR REPLACE TABLE {raw_table} AS
SELECT
  *,
  CAST(((rn - 1) % {num_batches}) + 1 AS INT) AS batch_id
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (ORDER BY file_size_bytes DESC, source_path) AS rn
  FROM {raw_table}
)
""")

batch_counts = spark.sql(f"""
  SELECT batch_id, COUNT(*) AS cnt, SUM(file_size_bytes) AS total_bytes
  FROM {raw_table}
  GROUP BY batch_id
  ORDER BY batch_id
""").collect()

print(f"Assigned {num_batches} batches (target batch_size={batch_size}) across {raw_count} documents:")
for row in batch_counts:
    mb = (row["total_bytes"] or 0) / (1024 * 1024)
    print(f"  Batch {row['batch_id']}: {row['cnt']} docs, {mb:.1f} MB")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build ai_parse_document options

# COMMAND ----------

opts = config.processing.ai_parse_options
image_volume_base = f"/Volumes/{config.catalog}/{config.schema}/{config.storage.image_volume}"
image_output_path = f"{image_volume_base}/{run_id}"

parse_options_parts = [f"'version', '{opts.version}'"]
if opts.save_page_images:
    parse_options_parts.append(f"'imageOutputPath', '{image_output_path}/'")
parse_options_parts.append(f"'descriptionElementTypes', '{opts.description_element_types}'")
parse_options_sql = ", ".join(parse_options_parts)

print(f"ai_parse_document options: map({parse_options_sql})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process batches with retry

# COMMAND ----------

parsed_table = config.fqn(config.storage.tables.parsed_documents)
log_table = config.fqn(config.storage.tables.processing_log)

max_retries = config.processing.max_retries
retry_delay = config.processing.retry_delay_seconds

batch_stats = {"completed": 0, "failed": 0, "total_docs": 0, "total_retries": 0}

for batch_num in range(1, num_batches + 1):
    batch_doc_count = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {raw_table} WHERE batch_id = {batch_num}"
    ).collect()[0]["cnt"]

    print(f"\n--- Batch {batch_num}/{num_batches} ({batch_doc_count} documents) ---")

    spark.sql(f"""
    UPDATE {log_table}
    SET status = 'processing',
        batch_id = {batch_num},
        started_at = current_timestamp()
    WHERE pipeline_run_id = '{run_id}'
      AND source_path IN (
        SELECT source_path FROM {raw_table} WHERE batch_id = {batch_num}
      )
    """)

    success = False
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            start_ts = time.time()

            spark.sql(f"""
            INSERT INTO {parsed_table}
            SELECT
              source_name,
              source_path,
              file_name,
              ai_parse_document(
                content,
                map({parse_options_sql})
              ) AS parsed_output,
              current_timestamp() AS parsed_at,
              '{run_id}' AS pipeline_run_id
            FROM {raw_table}
            WHERE batch_id = {batch_num}
            """)

            elapsed_ms = int((time.time() - start_ts) * 1000)

            spark.sql(f"""
            UPDATE {log_table}
            SET status = 'completed',
                attempt_number = {attempt},
                parse_duration_ms = {elapsed_ms},
                completed_at = current_timestamp()
            WHERE pipeline_run_id = '{run_id}'
              AND source_path IN (
                SELECT source_path FROM {raw_table} WHERE batch_id = {batch_num}
              )
            """)

            batch_stats["completed"] += 1
            batch_stats["total_docs"] += batch_doc_count
            success = True
            print(f"  Batch {batch_num} completed in {elapsed_ms}ms (attempt {attempt})")
            break

        except Exception as e:
            last_error = str(e)
            batch_stats["total_retries"] += 1
            print(f"  Attempt {attempt}/{max_retries} failed: {last_error[:200]}")

            if attempt < max_retries:
                delay = retry_delay * (2 ** (attempt - 1))
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)

    if not success:
        batch_stats["failed"] += 1
        print(f"  Batch {batch_num} FAILED after {max_retries} attempts.")

        spark.sql(f"""
        UPDATE {log_table}
        SET status = 'failed',
            attempt_number = {max_retries},
            error_message = '{last_error[:1000].replace("'", "''")}',
            completed_at = current_timestamp()
        WHERE pipeline_run_id = '{run_id}'
          AND source_path IN (
            SELECT source_path FROM {raw_table} WHERE batch_id = {batch_num}
          )
        """)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Update element/page counts for completed documents

# COMMAND ----------

spark.sql(f"""
MERGE INTO {log_table} AS log
USING (
  SELECT
    source_path,
    SIZE(CAST(parsed_output:document:elements AS ARRAY<STRING>)) AS elem_count,
    SIZE(CAST(parsed_output:document:pages AS ARRAY<STRING>)) AS page_count
  FROM {parsed_table}
  WHERE pipeline_run_id = '{run_id}'
) AS counts
ON log.source_path = counts.source_path
   AND log.pipeline_run_id = '{run_id}'
WHEN MATCHED THEN UPDATE SET
  log.elements_extracted = counts.elem_count,
  log.pages_parsed = counts.page_count
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

total_parsed = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {parsed_table} WHERE pipeline_run_id = '{run_id}'
""").collect()[0]["cnt"]

failed_count = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {log_table}
  WHERE pipeline_run_id = '{run_id}' AND status = 'failed'
""").collect()[0]["cnt"]

error_docs = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {parsed_table}
  WHERE pipeline_run_id = '{run_id}'
    AND parsed_output:error_status IS NOT NULL
    AND SIZE(CAST(parsed_output:error_status AS ARRAY<STRING>)) > 0
""").collect()[0]["cnt"]

print(f"--- Parse Summary ---")
print(f"Batches completed  : {batch_stats['completed']}/{num_batches}")
print(f"Batches failed     : {batch_stats['failed']}/{num_batches}")
print(f"Total retries      : {batch_stats['total_retries']}")
print(f"Documents parsed   : {total_parsed}")
print(f"Documents failed   : {failed_count}")
print(f"Docs with errors   : {error_docs} (parsed but had page-level errors)")
print(f"Pipeline run ID    : {run_id}")

dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="total_parsed", value=total_parsed)
