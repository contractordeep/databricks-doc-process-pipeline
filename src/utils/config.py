"""
Config loader for the document processing pipeline.

Reads pipeline_config.yml, resolves {catalog}/{schema} placeholders
from Databricks job parameters, and returns typed dataclasses.
"""

import re
import yaml
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceEntry:
    """
    A single document source. Common fields apply to all types.
    Connector-specific fields are optional and only used by their connector.
    The raw dict is preserved for connectors that need extra fields.
    """
    name: str
    type: str = "volume"
    path: str = ""
    paths: Optional[List[str]] = None
    file_pattern: str = "*.pdf"
    recursive: bool = True
    # SharePoint
    site_url: str = ""
    library: str = "Shared Documents"
    folder: str = "/"
    folders: Optional[List[str]] = None
    # Google Drive
    folder_id: str = ""
    folder_ids: Optional[List[str]] = None
    # ADLS
    storage_account: str = ""
    container: str = ""
    prefix: str = ""
    prefixes: Optional[List[str]] = None
    # Auth (plain dict -- varies per connector type)
    auth: Optional[dict] = None

    def get_paths(self) -> List[str]:
        """Return all paths for this source (supports both path and paths)."""
        result = []
        if self.paths:
            result.extend(self.paths)
        if self.path:
            result.append(self.path)
        return result if result else [""]

    def get_folders(self) -> List[str]:
        """Return all SharePoint folders (supports both folder and folders)."""
        result = []
        if self.folders:
            result.extend(self.folders)
        if self.folder and self.folder != "/":
            result.append(self.folder)
        return result if result else ["/"]

    def get_folder_ids(self) -> List[str]:
        """Return all Google Drive folder IDs (supports both folder_id and folder_ids)."""
        result = []
        if self.folder_ids:
            result.extend(self.folder_ids)
        if self.folder_id:
            result.append(self.folder_id)
        return result

    def get_prefixes(self) -> List[str]:
        """Return all ADLS prefixes (supports both prefix and prefixes)."""
        result = []
        if self.prefixes:
            result.extend(self.prefixes)
        if self.prefix:
            result.append(self.prefix)
        return result if result else [""]

    def to_dict(self) -> dict:
        """Convert back to a plain dict for passing to connectors."""
        from dataclasses import asdict
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AiParseOptions:
    version: str = "2.0"
    description_element_types: str = "*"
    save_page_images: bool = True


@dataclass
class ProcessingConfig:
    batch_size: int = 50
    max_retries: int = 3
    retry_delay_seconds: int = 10
    ai_parse_options: AiParseOptions = field(default_factory=AiParseOptions)


@dataclass
class AutoscaleConfig:
    min_workers: int = 2
    max_workers: int = 8


@dataclass
class ComputeConfig:
    spark_version: str = "17.1.x-scala2.12"
    node_type_id: str = "i3.xlarge"
    num_workers: int = 4
    autoscale: Optional[AutoscaleConfig] = None


@dataclass
class TablesConfig:
    document_registry: str = "document_registry"
    raw_documents: str = "raw_documents"
    parsed_documents: str = "parsed_documents"
    document_elements: str = "document_elements"
    document_pages: str = "document_pages"
    processing_log: str = "processing_log"


@dataclass
class StorageConfig:
    catalog: str = "main"
    schema: str = "doc_processing"
    image_volume: str = "parsed_images"
    staging_volume: str = "staging"
    tables: TablesConfig = field(default_factory=TablesConfig)


@dataclass
class PipelineConfig:
    sources: List[SourceEntry]
    processing: ProcessingConfig
    compute: ComputeConfig
    storage: StorageConfig

    @property
    def catalog(self) -> str:
        return self.storage.catalog

    @property
    def schema(self) -> str:
        return self.storage.schema

    def fqn(self, table_name: str) -> str:
        """Return fully-qualified table name: `catalog`.`schema`.`table` (backticks for names with -,_ etc.)."""
        return f"`{self.catalog}`.`{self.schema}`.`{table_name}`"


def _resolve_placeholders(obj, variables: dict):
    """Recursively replace {key} placeholders in strings with variable values."""
    if isinstance(obj, str):
        def replacer(match):
            key = match.group(1)
            return variables.get(key, match.group(0))
        return re.sub(r"\{(\w+)\}", replacer, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_placeholders(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_placeholders(item, variables) for item in obj]
    return obj


def _dict_to_dataclass(cls, data: dict):
    """Recursively instantiate a dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return None
    field_names = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {}
    for k, v in data.items():
        if k not in field_names:
            continue
        field_obj = cls.__dataclass_fields__[k]
        field_type = field_obj.type

        if hasattr(field_type, "__dataclass_fields__"):
            filtered[k] = _dict_to_dataclass(field_type, v) if isinstance(v, dict) else v
        elif str(field_type).startswith("typing.Optional"):
            inner = field_type.__args__[0]
            if hasattr(inner, "__dataclass_fields__") and isinstance(v, dict):
                filtered[k] = _dict_to_dataclass(inner, v)
            else:
                filtered[k] = v
        else:
            filtered[k] = v
    return cls(**filtered)


def load_config(config_path: str, variables: Optional[dict] = None) -> PipelineConfig:
    """
    Load pipeline_config.yml and resolve placeholders.

    Args:
        config_path: Absolute path to pipeline_config.yml
        variables: Dict of placeholder values, e.g. {"catalog": "main", "schema": "doc_processing"}

    Returns:
        Fully resolved PipelineConfig dataclass
    """
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    if variables:
        raw = _resolve_placeholders(raw, variables)

    sources_data = raw.get("sources", [])
    sources = []
    for s in sources_data:
        entry = _dict_to_dataclass(SourceEntry, s)
        if entry.auth is None and "auth" in s:
            entry.auth = s["auth"]
        sources.append(entry)
    if not sources:
        raise ValueError("pipeline_config.yml must define at least one entry under 'sources'")

    processing_data = raw.get("processing", {})
    if processing_data.get("ai_parse_options"):
        processing_data["ai_parse_options"] = _dict_to_dataclass(
            AiParseOptions, processing_data["ai_parse_options"]
        )
    processing = _dict_to_dataclass(ProcessingConfig, processing_data)

    compute = _dict_to_dataclass(ComputeConfig, raw.get("compute", {}))

    storage_data = raw.get("storage", {})
    if storage_data.get("tables"):
        storage_data["tables"] = _dict_to_dataclass(TablesConfig, storage_data["tables"])
    storage = _dict_to_dataclass(StorageConfig, storage_data)

    return PipelineConfig(
        sources=sources,
        processing=processing,
        compute=compute,
        storage=storage,
    )
