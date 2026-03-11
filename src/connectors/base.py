"""
Abstract base connector and shared data models for document source connectors.
"""

import hashlib
import fnmatch
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FileRef:
    """A file discovered at an external source."""
    original_path: str
    file_name: str
    file_size_bytes: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class StagedFile:
    """A file that has been downloaded/staged into a Databricks Volume."""
    original_path: str
    staging_path: str
    file_name: str
    file_size_bytes: int
    content_hash: str


class BaseConnector(ABC):
    """
    Abstract connector that all source connectors must implement.

    Each connector knows how to:
    1. List files at the source that match a pattern
    2. Download those files into a staging volume
    """

    def __init__(self, source_config: dict, dbutils=None):
        """
        Args:
            source_config: The source entry dict from pipeline_config.yml
            dbutils: Databricks dbutils instance (for secret scopes, fs operations)
        """
        self.config = source_config
        self.dbutils = dbutils
        self.source_name = source_config.get("name", "unknown")
        self.file_pattern = source_config.get("file_pattern", "*")
        self.recursive = source_config.get("recursive", True)

    def _get_secret(self, scope: str, key: str) -> str:
        """Retrieve a secret from Databricks Secret Scopes."""
        if self.dbutils is None:
            raise RuntimeError("dbutils is required to access secret scopes")
        return self.dbutils.secrets.get(scope=scope, key=key)

    def _matches_pattern(self, file_name: str) -> bool:
        """Check if a file name matches the configured glob pattern."""
        pattern = self.file_pattern
        if pattern.startswith("*.{") and pattern.endswith("}"):
            extensions = pattern[3:-1].split(",")
            return any(file_name.lower().endswith(f".{ext.strip()}") for ext in extensions)
        return fnmatch.fnmatch(file_name.lower(), pattern.lower())

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        return hashlib.md5(content).hexdigest()

    @abstractmethod
    def list_files(self) -> List[FileRef]:
        """Discover files at the source matching the configured pattern."""

    @abstractmethod
    def download_files(
        self, files: List[FileRef], staging_dir: str
    ) -> List[StagedFile]:
        """
        Download files to the staging volume directory.

        Args:
            files: Files to download (from list_files)
            staging_dir: Target directory in a Databricks Volume, e.g.
                         /Volumes/catalog/schema/staging/source_name/

        Returns:
            List of StagedFile with staging_path populated
        """
