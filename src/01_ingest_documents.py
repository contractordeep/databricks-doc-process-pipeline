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
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

sys.path.insert(0, os.path.dirname(config_path.replace("/Workspace", "/Workspace")))
from src.utils.config import load_config

config = load_config(config_path, variables={"catalog": catalog, "schema": schema})

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
staging_base = f"/Volumes/{config.catalog}/{config.schema}/{config.storage.staging_volume}"

# Collect all distinct staging directories from the registry for this run
staging_dirs = spark.sql(f"""
  SELECT DISTINCT source_name, source_type, staging_path
  FROM {registry_table}
  WHERE pipeline_run_id = '{run_id}' AND sync_status = 'synced'
""").collect()

# Build a set of all staging root directories to scan
# For volume sources, staging_path is the original path (could be anywhere)
# For external sources, staging_path is under the staging volume

# Group staging paths by their parent directories for efficient read_files calls
from collections import defaultdict
source_dirs = defaultdict(set)
for row in staging_dirs:
    parent = os.path.dirname(row["staging_path"])
    source_dirs[row["source_name"]].add(parent)

union_parts = []
for source_name, dirs in source_dirs.items():
    for d in dirs:
        union_parts.append(f"""
        SELECT
          '{source_name}' AS source_name,
          _metadata.file_path AS source_path,
          _metadata.file_name AS file_name,
          _metadata.file_size AS file_size_bytes,
          _metadata.file_modification_time AS source_modified_at,
          content,
          current_timestamp() AS ingested_at,
          '{run_id}' AS pipeline_run_id
        FROM read_files(
          '{d}',
          format => 'binaryFile',
          recursiveFileLookup => false
        )
        WHERE _metadata.file_path IN (
          SELECT staging_path FROM {registry_table}
          WHERE pipeline_run_id = '{run_id}'
            AND sync_status = 'synced'
            AND source_name = '{source_name}'
        )
        """)

if not union_parts:
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
