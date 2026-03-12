# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Flatten Elements
# MAGIC
# MAGIC Explodes the VARIANT output from `ai_parse_document` into
# MAGIC queryable gold tables: `document_elements` and `document_pages`.

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

run_id = dbutils.jobs.taskValues.get(taskKey="parse_documents", key="run_id")
total_parsed = dbutils.jobs.taskValues.get(taskKey="parse_documents", key="total_parsed")

print(f"Pipeline run ID: {run_id}")
print(f"Documents to flatten: {total_parsed}")

if total_parsed == 0:
    print("No new documents to flatten. Nothing to do.")
    dbutils.notebook.exit("skip")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create document_elements (Gold)

# COMMAND ----------

parsed_table = config.fqn(config.storage.tables.parsed_documents)
elements_table = config.fqn(config.storage.tables.document_elements)
pages_table = config.fqn(config.storage.tables.document_pages)
log_table = config.fqn(config.storage.tables.processing_log)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {elements_table} (
  source_name STRING,
  source_path STRING,
  file_name STRING,
  element_id INT,
  element_type STRING,
  content STRING,
  ai_description STRING,
  bounding_box_json STRING,
  page_id INT,
  bbox_index INT,
  bbox_x1 INT,
  bbox_y1 INT,
  bbox_x2 INT,
  bbox_y2 INT,
  has_parse_errors BOOLEAN,
  parsed_at TIMESTAMP,
  pipeline_run_id STRING
)
CLUSTER BY (source_name, file_name, page_id)
""")

# Remove stale rows for documents being re-processed (handles changed content)
docs_in_run = spark.sql(f"""
  SELECT DISTINCT source_path FROM {parsed_table} WHERE pipeline_run_id = '{run_id}'
""").collect()
if docs_in_run:
    paths = [row["source_path"].replace("'", "''") for row in docs_in_run]
    source_paths = ", ".join(f"'{p}'" for p in paths)
    spark.sql(f"DELETE FROM {elements_table} WHERE source_path IN ({source_paths})")
    print(f"Cleared stale element rows for {len(docs_in_run)} documents.")

spark.sql(f"""
INSERT INTO {elements_table}
SELECT
  p.source_name,
  p.source_path,
  p.file_name,
  elem.value:id::INT AS element_id,
  elem.value:type::STRING AS element_type,
  elem.value:content::STRING AS content,
  elem.value:description::STRING AS ai_description,
  to_json(elem.value:bbox) AS bounding_box_json,
  bb.value:page_id::INT AS page_id,
  CAST(bb.pos AS INT) AS bbox_index,
  bb.value:coord[0]::INT AS bbox_x1,
  bb.value:coord[1]::INT AS bbox_y1,
  bb.value:coord[2]::INT AS bbox_x2,
  bb.value:coord[3]::INT AS bbox_y2,
  CASE
    WHEN p.parsed_output:error_status IS NOT NULL
     AND SIZE(CAST(p.parsed_output:error_status AS ARRAY<STRING>)) > 0
    THEN true ELSE false
  END AS has_parse_errors,
  p.parsed_at,
  p.pipeline_run_id
FROM {parsed_table} p,
  LATERAL VARIANT_EXPLODE(p.parsed_output:document:elements) AS elem,
  LATERAL VARIANT_EXPLODE(elem.value:bbox) AS bb
WHERE p.pipeline_run_id = '{run_id}'
""")

element_count = spark.table(elements_table).filter(f"pipeline_run_id = '{run_id}'").count()
print(f"Inserted {element_count} elements into {elements_table}.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create document_pages (Gold)

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {pages_table} (
  source_name STRING,
  source_path STRING,
  file_name STRING,
  page_number INT,
  image_uri STRING,
  has_parse_errors BOOLEAN,
  page_has_error BOOLEAN,
  parsed_at TIMESTAMP,
  pipeline_run_id STRING
)
CLUSTER BY (source_name, file_name)
""")

# Remove stale rows for documents being re-processed
if docs_in_run:
    spark.sql(f"DELETE FROM {pages_table} WHERE source_path IN ({source_paths})")
    print(f"Cleared stale page rows for {len(docs_in_run)} documents.")

spark.sql(f"""
INSERT INTO {pages_table}
SELECT
  p.source_name,
  p.source_path,
  p.file_name,
  page.value:id::INT AS page_number,
  page.value:image_uri::STRING AS image_uri,
  CASE
    WHEN p.parsed_output:error_status IS NOT NULL
     AND SIZE(CAST(p.parsed_output:error_status AS ARRAY<STRING>)) > 0
    THEN true ELSE false
  END AS has_parse_errors,
  CASE
    WHEN err.error_page_id IS NOT NULL THEN true
    ELSE false
  END AS page_has_error,
  p.parsed_at,
  p.pipeline_run_id
FROM {parsed_table} p,
  LATERAL VARIANT_EXPLODE(p.parsed_output:document:pages) AS page
LEFT JOIN (
  SELECT
    pe.source_path,
    es.value:page_id::INT AS error_page_id
  FROM {parsed_table} pe,
    LATERAL VARIANT_EXPLODE(pe.parsed_output:error_status) AS es
  WHERE pe.pipeline_run_id = '{run_id}'
) err
  ON p.source_path = err.source_path
  AND page.value:id::INT = err.error_page_id
WHERE p.pipeline_run_id = '{run_id}'
""")

page_count = spark.table(pages_table).filter(f"pipeline_run_id = '{run_id}'").count()
print(f"Inserted {page_count} pages into {pages_table}.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Update processing_log with final counts

# COMMAND ----------

spark.sql(f"""
MERGE INTO {log_table} AS log
USING (
  SELECT
    source_path,
    COUNT(*) AS elem_count
  FROM {elements_table}
  WHERE pipeline_run_id = '{run_id}'
  GROUP BY source_path
) AS counts
ON log.source_path = counts.source_path
   AND log.pipeline_run_id = '{run_id}'
WHEN MATCHED THEN UPDATE SET
  log.elements_extracted = counts.elem_count
""")

spark.sql(f"""
MERGE INTO {log_table} AS log
USING (
  SELECT
    source_path,
    COUNT(*) AS page_cnt
  FROM {pages_table}
  WHERE pipeline_run_id = '{run_id}'
  GROUP BY source_path
) AS counts
ON log.source_path = counts.source_path
   AND log.pipeline_run_id = '{run_id}'
WHEN MATCHED THEN UPDATE SET
  log.pages_parsed = counts.page_cnt
""")

print("Updated processing_log with element and page counts.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

element_type_dist = spark.sql(f"""
  SELECT element_type, COUNT(*) AS cnt
  FROM {elements_table}
  WHERE pipeline_run_id = '{run_id}'
  GROUP BY element_type
  ORDER BY cnt DESC
""").collect()

unique_docs = spark.sql(f"""
  SELECT COUNT(DISTINCT file_name) AS cnt
  FROM {elements_table}
  WHERE pipeline_run_id = '{run_id}'
""").collect()[0]["cnt"]

completed_count = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {log_table}
  WHERE pipeline_run_id = '{run_id}' AND status = 'completed'
""").collect()[0]["cnt"]

failed_count = spark.sql(f"""
  SELECT COUNT(*) AS cnt FROM {log_table}
  WHERE pipeline_run_id = '{run_id}' AND status = 'failed'
""").collect()[0]["cnt"]

print(f"--- Flatten Summary ---")
print(f"Documents processed : {unique_docs}")
print(f"Total elements      : {element_count}")
print(f"Total pages         : {page_count}")
print(f"Completed docs      : {completed_count}")
print(f"Failed docs         : {failed_count}")
print(f"\nElement type distribution:")
for row in element_type_dist:
    print(f"  {row['element_type']:20s} : {row['cnt']}")

print(f"\n--- Output Tables ---")
print(f"  Elements : {elements_table}")
print(f"  Pages    : {pages_table}")
print(f"  Log      : {log_table}")
print(f"  Parsed   : {parsed_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Show sample results

# COMMAND ----------

display(
    spark.sql(f"""
    SELECT file_name, element_id, element_type, LEFT(content, 200) AS content_preview,
           page_id, bbox_index, bbox_x1, bbox_y1, bbox_x2, bbox_y2, has_parse_errors
    FROM {elements_table}
    WHERE pipeline_run_id = '{run_id}'
    ORDER BY file_name, element_id, bbox_index
    LIMIT 50
    """)
)
