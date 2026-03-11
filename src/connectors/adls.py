"""
Azure Data Lake Storage Gen2 connector: lists and downloads blobs
from an ADLS container using azure-storage-blob.

Required secrets in the configured secret scope:
  - account_key_secret: Storage account access key
  OR
  - connection_string_key: Full connection string
"""

import os
from typing import List

from azure.storage.blob import BlobServiceClient

from src.connectors import register
from src.connectors.base import BaseConnector, FileRef, StagedFile


@register("adls")
class ADLSConnector(BaseConnector):

    def __init__(self, source_config: dict, dbutils=None):
        super().__init__(source_config, dbutils=dbutils)
        auth_cfg = source_config.get("auth", {})
        scope = auth_cfg.get("secret_scope", "")

        storage_account = source_config.get("storage_account", "")
        self._container = source_config.get("container", "")
        self._prefixes = [p.strip("/") for p in (source_config.get("prefixes") or [])]
        single_prefix = source_config.get("prefix", "").strip("/")
        if single_prefix:
            self._prefixes.append(single_prefix)
        if not self._prefixes:
            self._prefixes = [""]

        if auth_cfg.get("connection_string_key"):
            conn_str = self._get_secret(scope, auth_cfg["connection_string_key"])
            self._blob_service = BlobServiceClient.from_connection_string(conn_str)
        else:
            account_key = self._get_secret(scope, auth_cfg.get("account_key_secret", "storage-account-key"))
            account_url = f"https://{storage_account}.blob.core.windows.net"
            self._blob_service = BlobServiceClient(
                account_url=account_url, credential=account_key
            )

        self._container_client = self._blob_service.get_container_client(self._container)

    def list_files(self) -> List[FileRef]:
        results = []
        for pfx in self._prefixes:
            prefix = f"{pfx}/" if pfx else ""
            blobs = self._container_client.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                if blob.size == 0:
                    continue

                file_name = blob.name.split("/")[-1]

                if not self.recursive and blob.name.count("/") > prefix.count("/"):
                    continue

                if not self._matches_pattern(file_name):
                    continue

                results.append(FileRef(
                    original_path=f"abfss://{self._container}@{self._blob_service.account_name}.dfs.core.windows.net/{blob.name}",
                    file_name=file_name,
                    file_size_bytes=blob.size,
                    metadata={"blob_name": blob.name},
                ))

        return results

    def download_files(
        self, files: List[FileRef], staging_dir: str
    ) -> List[StagedFile]:
        os.makedirs(staging_dir, exist_ok=True)
        staged = []

        for f in files:
            blob_name = f.metadata["blob_name"]
            blob_client = self._container_client.get_blob_client(blob_name)

            content = blob_client.download_blob().readall()

            dest = os.path.join(staging_dir, f.file_name)
            if os.path.exists(dest):
                name, ext = os.path.splitext(f.file_name)
                short_hash = self._compute_hash(content)[:8]
                dest = os.path.join(staging_dir, f"{name}_{short_hash}{ext}")

            with open(dest, "wb") as out:
                out.write(content)

            staged.append(StagedFile(
                original_path=f.original_path,
                staging_path=dest,
                file_name=os.path.basename(dest),
                file_size_bytes=len(content),
                content_hash=self._compute_hash(content),
            ))

        return staged
