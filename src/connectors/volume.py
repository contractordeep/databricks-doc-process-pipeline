"""
Volume connector: lists files from one or more Databricks Volume paths.
No download step needed -- files are already accessible.
Supports both `path` (single) and `paths` (list) in config.
"""

import os
from typing import List

from src.connectors import register
from src.connectors.base import BaseConnector, FileRef, StagedFile


@register("volume")
class VolumeConnector(BaseConnector):
    """Connector for files already in Databricks Unity Catalog Volumes."""

    def list_files(self) -> List[FileRef]:
        volume_paths = self.config.get("paths") or []
        single_path = self.config.get("path", "")
        if single_path:
            volume_paths.append(single_path)

        if not volume_paths:
            return []

        results = []
        for vp in volume_paths:
            results.extend(self._scan_dir(vp))
        return results

    def _scan_dir(self, path: str) -> List[FileRef]:
        results = []
        try:
            entries = self.dbutils.fs.ls(path)
        except Exception:
            return results

        for entry in entries:
            if entry.isDir():
                if self.recursive:
                    results.extend(self._scan_dir(entry.path))
            else:
                file_name = entry.name
                if self._matches_pattern(file_name):
                    fuse_path = entry.path
                    if fuse_path.startswith("dbfs:"):
                        fuse_path = fuse_path.replace("dbfs:", "", 1)
                    results.append(FileRef(
                        original_path=fuse_path,
                        file_name=file_name,
                        file_size_bytes=entry.size,
                    ))
        return results

    def download_files(
        self, files: List[FileRef], staging_dir: str
    ) -> List[StagedFile]:
        """No-op for volume sources: staging_path = original_path."""
        staged = []
        for f in files:
            content_hash = ""
            try:
                with open(f.original_path, "rb") as fh:
                    content_hash = self._compute_hash(fh.read())
            except Exception:
                pass

            staged.append(StagedFile(
                original_path=f.original_path,
                staging_path=f.original_path,
                file_name=f.file_name,
                file_size_bytes=f.file_size_bytes,
                content_hash=content_hash,
            ))
        return staged
