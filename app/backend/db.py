"""
Database connection layer using databricks-sql-connector.
Uses SDK Config() for auto-authentication in Databricks Apps.
"""

import os
from typing import Any
from databricks import sql as dbsql
from databricks.sdk.core import Config


_connection = None


def _get_catalog() -> str:
    return os.getenv("DATABRICKS_CATALOG", "main")


def _get_schema() -> str:
    return os.getenv("DATABRICKS_SCHEMA", "doc_processing")


def fqn(table: str) -> str:
    """Return fully-qualified table name with backticks for names containing -,_ etc."""
    return f"`{_get_catalog()}`.`{_get_schema()}`.`{table}`"


def get_connection():
    global _connection
    if _connection is None:
        cfg = Config()
        warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
        _connection = dbsql.connect(
            server_hostname=cfg.host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            credentials_provider=lambda: cfg.authenticate,
        )
    return _connection


def execute_query(query: str, params: dict[str, Any] | None = None) -> list[dict]:
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
