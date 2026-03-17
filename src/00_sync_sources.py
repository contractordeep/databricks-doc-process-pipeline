# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Sync Sources
# MAGIC
# MAGIC Iterates configured sources, downloads external files to a staging
# MAGIC volume, and registers every document in the `document_registry` table.

# COMMAND ----------

# MAGIC %pip install pyyaml msal requests google-api-python-client google-auth azure-storage-blob
# MAGIC %restart_python

# COMMAND ----------

import os
import sys
import uuid
import traceback

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load configuration

# COMMAND ----------

config_path = dbutils.widgets.get("config_path")

sys.path.insert(0, os.path.dirname(os.path.dirname(config_path)))
from src.utils.config import load_config

config = load_config(config_path)

run_id = str(uuid.uuid4())
print(f"Pipeline run ID: {run_id}")
print(f"Target: {config.catalog}.{config.schema}")
print(f"Sources configured: {len(config.sources)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create schema, volumes, and registry table
# MAGIC
# MAGIC Schema and volumes are created from `config/pipeline_config.yml` so you only set catalog and schema there (no separate volumes.yml).

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{config.catalog}`.`{config.schema}`")

# Create volumes used by the pipeline so users only configure catalog/schema in pipeline_config.yml
for vol_name in (config.storage.staging_volume, config.storage.image_volume):
    spark.sql(f"CREATE VOLUME IF NOT EXISTS `{config.catalog}`.`{config.schema}`.`{vol_name}`")

registry_table = config.fqn(config.storage.tables.document_registry)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {registry_table} (
  document_id STRING,
  source_name STRING,
  source_type STRING,
  original_path STRING,
  staging_path STRING,
  file_name STRING,
  file_size_bytes LONG,
  content_hash STRING,
  sync_status STRING,
  sync_error STRING,
  synced_at TIMESTAMP,
  registered_at TIMESTAMP,
  pipeline_run_id STRING
)
CLUSTER BY (source_name, sync_status)
""")

print(f"Registry table: {registry_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sync each source

# COMMAND ----------

from src.connectors import get_connector

staging_base = f"/Volumes/{config.catalog}/{config.schema}/{config.storage.staging_volume}"
os.makedirs(staging_base, exist_ok=True)

sync_stats = {}

for source in config.sources:
    source_name = source.name
    source_type = source.type
    staging_dir = os.path.join(staging_base, source_name)

    print(f"\n=== Syncing source: {source_name} (type={source_type}) ===")

    try:
        connector = get_connector(source.to_dict(), dbutils=dbutils)
    except Exception as e:
        print(f"  FAILED to initialize connector: {e}")
        sync_stats[source_name] = {"listed": 0, "synced": 0, "failed": 1}
        continue

    # List files
    try:
        files = connector.list_files()
        print(f"  Discovered {len(files)} files")
    except Exception as e:
        print(f"  FAILED to list files: {e}")
        sync_stats[source_name] = {"listed": 0, "synced": 0, "failed": 1}
        continue

    if not files:
        print(f"  No files found, skipping.")
        sync_stats[source_name] = {"listed": 0, "synced": 0, "failed": 0}
        continue

    # Download / stage files
    synced_count = 0
    failed_count = 0
    registry_rows = []

    try:
        staged_files = connector.download_files(files, staging_dir)

        for sf in staged_files:
            doc_id = connector._compute_hash(
                f"{source_name}:{sf.original_path}".encode()
            )
            registry_rows.append({
                "document_id": doc_id,
                "source_name": source_name,
                "source_type": source_type,
                "original_path": sf.original_path,
                "staging_path": sf.staging_path,
                "file_name": sf.file_name,
                "file_size_bytes": sf.file_size_bytes,
                "content_hash": sf.content_hash,
                "sync_status": "synced",
                "sync_error": None,
                "pipeline_run_id": run_id,
            })
            synced_count += 1

    except Exception as e:
        print(f"  Batch download failed: {e}")
        # Fall back to per-file download
        for f in files:
            try:
                staged = connector.download_files([f], staging_dir)
                sf = staged[0]
                doc_id = connector._compute_hash(
                    f"{source_name}:{sf.original_path}".encode()
                )
                registry_rows.append({
                    "document_id": doc_id,
                    "source_name": source_name,
                    "source_type": source_type,
                    "original_path": sf.original_path,
                    "staging_path": sf.staging_path,
                    "file_name": sf.file_name,
                    "file_size_bytes": sf.file_size_bytes,
                    "content_hash": sf.content_hash,
                    "sync_status": "synced",
                    "sync_error": None,
                    "pipeline_run_id": run_id,
                })
                synced_count += 1
            except Exception as file_err:
                doc_id = connector._compute_hash(
                    f"{source_name}:{f.original_path}".encode()
                )
                registry_rows.append({
                    "document_id": doc_id,
                    "source_name": source_name,
                    "source_type": source_type,
                    "original_path": f.original_path,
                    "staging_path": None,
                    "file_name": f.file_name,
                    "file_size_bytes": f.file_size_bytes,
                    "content_hash": None,
                    "sync_status": "failed",
                    "sync_error": str(file_err)[:1000],
                    "pipeline_run_id": run_id,
                })
                failed_count += 1
                print(f"    FAILED {f.file_name}: {file_err}")

    # Upsert registry rows: update existing documents, insert new ones
    if registry_rows:
        from pyspark.sql.types import (
            StructType, StructField, StringType, LongType
        )
        from pyspark.sql.functions import current_timestamp

        reg_schema = StructType([
            StructField("document_id", StringType(), False),
            StructField("source_name", StringType(), False),
            StructField("source_type", StringType(), False),
            StructField("original_path", StringType(), True),
            StructField("staging_path", StringType(), True),
            StructField("file_name", StringType(), True),
            StructField("file_size_bytes", LongType(), True),
            StructField("content_hash", StringType(), True),
            StructField("sync_status", StringType(), False),
            StructField("sync_error", StringType(), True),
            StructField("pipeline_run_id", StringType(), False),
        ])

        df = spark.createDataFrame(registry_rows, schema=reg_schema)
        df = df.withColumn("synced_at", current_timestamp())
        df = df.withColumn("registered_at", current_timestamp())
        df.createOrReplaceTempView("_new_registry_rows")

        spark.sql(f"""
        MERGE INTO {registry_table} AS target
        USING _new_registry_rows AS source
        ON target.document_id = source.document_id
        WHEN MATCHED THEN UPDATE SET
          target.staging_path = source.staging_path,
          target.file_size_bytes = source.file_size_bytes,
          target.content_hash = source.content_hash,
          target.sync_status = source.sync_status,
          target.sync_error = source.sync_error,
          target.synced_at = source.synced_at,
          target.pipeline_run_id = source.pipeline_run_id
        WHEN NOT MATCHED THEN INSERT *
        """)

    sync_stats[source_name] = {
        "listed": len(files),
        "synced": synced_count,
        "failed": failed_count,
    }
    print(f"  Listed: {len(files)} | Synced: {synced_count} | Failed: {failed_count}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

total_synced = sum(s["synced"] for s in sync_stats.values())
total_failed = sum(s["failed"] for s in sync_stats.values())
total_listed = sum(s["listed"] for s in sync_stats.values())

print(f"--- Sync Summary ---")
print(f"Pipeline run ID    : {run_id}")
print(f"Sources processed  : {len(sync_stats)}")
print(f"Files discovered   : {total_listed}")
print(f"Files synced       : {total_synced}")
print(f"Files failed       : {total_failed}")
print(f"Registry table     : {registry_table}")
print(f"\nPer-source breakdown:")
for name, stats in sync_stats.items():
    print(f"  {name:20s} : listed={stats['listed']}  synced={stats['synced']}  failed={stats['failed']}")

dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="total_synced", value=total_synced)
