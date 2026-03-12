# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Ingest Documents
# MAGIC
# MAGIC Reads the `document_registry` (populated by 00_sync_sources) to load
# MAGIC binary content from staging paths into the `raw_documents` table
# MAGIC and initializes the `processing_log`.

# COMMAND ----------

# MAGIC %pip install pyyaml
# MAGIC %restart_python

# COMMAND ----------

import os
import sys

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load configuration

# COMMAND ----------

config_path = dbutils.widgets.get("config_path")

sys.path.insert(0, os.path.dirname(os.path.dirname(config_path)))
from src.utils.config import load_config

config = load_config(config_path)

run_id = dbutils.jobs.taskValues.get(taskKey="sync_sources", key="run_id")
total_synced = dbutils.jobs.taskValues.get(taskKey="sync_sources", key="total_synced")

print(f"Pipeline run ID: {run_id}")
print(f"Target: {config.catalog}.{config.schema}")
print(f"Documents synced: {total_synced}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create tables

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {config.fqn(config.storage.tables.processing_log)} (
  document_id STRING,
  source_name STRING,
  source_path STRING,
  file_name STRING,
  status STRING,
  batch_id INT,
  attempt_number INT,
  error_message STRING,
  elements_extracted INT,
  pages_parsed INT,
  parse_duration_ms LONG,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  pipeline_run_id STRING
)
CLUSTER BY (pipeline_run_id, status)
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {config.fqn(config.storage.tables.parsed_documents)} (
  source_name STRING,
  source_path STRING,
  file_name STRING,
  parsed_output VARIANT,
  parsed_at TIMESTAMP,
  pipeline_run_id STRING
)
CLUSTER BY (source_name, file_name)
""")

print("Tables ensured.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load binary content from registry into raw_documents
# MAGIC
# MAGIC Reads the document_registry for all synced documents in this run,
# MAGIC then joins with `read_files` on the staging paths to get binary content.

# COMMAND ----------

registry_table = config.fqn(config.storage.tables.document_registry)
raw_table = config.fqn(config.storage.tables.raw_documents)
parsed_table = config.fqn(config.storage.tables.parsed_documents)

total_synced_count = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {registry_table}
  WHERE pipeline_run_id = '{run_id}' AND sync_status = 'synced'
""").collect()[0]["cnt"]

synced_files = spark.sql(f"""
  SELECT r.source_name, r.staging_path, r.file_name, r.file_size_bytes
  FROM {registry_table} r
  WHERE r.pipeline_run_id = '{run_id}'
    AND r.sync_status = 'synced'
    AND r.content_hash NOT IN (
      SELECT DISTINCT reg.content_hash
      FROM {parsed_table} pd
      JOIN {registry_table} reg ON pd.source_path = reg.staging_path
      WHERE reg.content_hash IS NOT NULL
    )
""").collect()

skipped = total_synced_count - len(synced_files)
print(f"Synced files: {total_synced_count} | Already parsed (skipped): {skipped} | To process: {len(synced_files)}")

if not synced_files:
    print("WARNING: No synced documents found in registry. raw_documents will be empty.")
    spark.sql(f"""
    CREATE OR REPLACE TABLE {raw_table} (
      source_name STRING,
      source_path STRING,
      file_name STRING,
      file_size_bytes LONG,
      source_modified_at TIMESTAMP,
      content BINARY,
      ingested_at TIMESTAMP,
      pipeline_run_id STRING
    )
    """)
else:
    union_parts = []
    for row in synced_files:
        path = row["staging_path"].replace("'", "''")
        src = row["source_name"].replace("'", "''")
        union_parts.append(f"""
        SELECT
          '{src}' AS source_name,
          '{path}' AS source_path,
          '{row["file_name"].replace("'", "''")}' AS file_name,
          {row["file_size_bytes"]} AS file_size_bytes,
          _metadata.file_modification_time AS source_modified_at,
          content,
          current_timestamp() AS ingested_at,
          '{run_id}' AS pipeline_run_id
        FROM read_files('{path}', format => 'binaryFile')
        """)

    union_sql = "\n        UNION ALL\n".join(union_parts)
    spark.sql(f"""
    CREATE OR REPLACE TABLE {raw_table} AS
    {union_sql}
    """)

raw_count = spark.table(raw_table).count()

per_source = spark.sql(f"""
  SELECT source_name, COUNT(*) AS cnt
  FROM {raw_table}
  GROUP BY source_name
  ORDER BY source_name
""").collect()

print(f"Ingested {raw_count} documents into {raw_table}")
for row in per_source:
    print(f"  {row['source_name']:20s} : {row['cnt']} documents")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize processing log

# COMMAND ----------

spark.sql(f"""
INSERT INTO {config.fqn(config.storage.tables.processing_log)}
SELECT
  md5(source_path) AS document_id,
  source_name,
  source_path,
  file_name,
  'queued' AS status,
  NULL AS batch_id,
  0 AS attempt_number,
  NULL AS error_message,
  NULL AS elements_extracted,
  NULL AS pages_parsed,
  NULL AS parse_duration_ms,
  current_timestamp() AS started_at,
  NULL AS completed_at,
  '{run_id}' AS pipeline_run_id
FROM {raw_table}
""")

print(f"Initialized processing_log with {raw_count} queued documents.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

total_bytes = spark.sql(f"""
  SELECT COALESCE(SUM(file_size_bytes), 0) AS total FROM {raw_table}
""").collect()[0]["total"]

total_mb = total_bytes / (1024 * 1024)

print(f"--- Ingestion Summary ---")
print(f"Documents ingested : {raw_count}")
print(f"Total size         : {total_mb:.2f} MB")
print(f"Pipeline run ID    : {run_id}")
print(f"Raw documents table: {raw_table}")
print(f"Registry table     : {registry_table}")

dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="raw_count", value=raw_count)
