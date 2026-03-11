"""
Connector factory: maps source type strings to connector classes.
"""

from src.connectors.base import BaseConnector


_REGISTRY = {}


def register(type_name: str):
    """Decorator to register a connector class for a source type."""
    def wrapper(cls):
        _REGISTRY[type_name] = cls
        return cls
    return wrapper


def get_connector(source_config: dict, dbutils=None) -> BaseConnector:
    """
    Instantiate the correct connector for a source config entry.

    Args:
        source_config: A single source dict from pipeline_config.yml
        dbutils: Databricks dbutils instance

    Raises:
        ValueError: If the source type is not supported
    """
    source_type = source_config.get("type", "volume")

    if source_type not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported source type '{source_type}'. Supported: {supported}"
        )

    cls = _REGISTRY[source_type]
    return cls(source_config, dbutils=dbutils)


# Import connectors so they self-register via @register decorator
import src.connectors.volume  # noqa: E402, F401
import src.connectors.sharepoint  # noqa: E402, F401
import src.connectors.google_drive  # noqa: E402, F401
import src.connectors.adls  # noqa: E402, F401
