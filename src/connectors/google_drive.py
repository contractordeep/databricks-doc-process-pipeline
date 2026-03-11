"""
Google Drive connector: lists and downloads files from a Google Drive folder
using a service account.

Required secrets in the configured secret scope:
  - service_account_key: JSON string of the service account credentials

The service account must have read access to the target folder
(share the folder with the service account email).
"""

import io
import os
import json
from typing import List

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from src.connectors import register
from src.connectors.base import BaseConnector, FileRef, StagedFile

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "image/jpeg",
    "image/png",
}

# Google Workspace docs need to be exported to a supported format
EXPORT_MAP = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


@register("google_drive")
class GoogleDriveConnector(BaseConnector):

    def __init__(self, source_config: dict, dbutils=None):
        super().__init__(source_config, dbutils=dbutils)
        auth_cfg = source_config.get("auth", {})
        scope = auth_cfg.get("secret_scope", "")
        sa_json = self._get_secret(scope, auth_cfg.get("service_account_key", "sa-credentials-json"))
        creds_info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._folder_ids = list(source_config.get("folder_ids") or [])
        single_id = source_config.get("folder_id", "")
        if single_id:
            self._folder_ids.append(single_id)

    def list_files(self) -> List[FileRef]:
        results = []
        for fid in self._folder_ids:
            results.extend(self._list_folder(fid))
        return results

    def _list_folder(self, folder_id: str) -> List[FileRef]:
        results = []
        page_token = None

        while True:
            resp = self._service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, size, mimeType)",
                pageSize=1000,
                pageToken=page_token,
            ).execute()

            for item in resp.get("files", []):
                mime = item.get("mimeType", "")

                if mime == "application/vnd.google-apps.folder":
                    if self.recursive:
                        results.extend(self._list_folder(item["id"]))
                    continue

                is_native = mime in SUPPORTED_MIME_TYPES
                is_exportable = mime in EXPORT_MAP
                if not (is_native or is_exportable):
                    continue

                file_name = item["name"]
                if is_exportable:
                    _, ext = EXPORT_MAP[mime]
                    if not file_name.endswith(ext):
                        file_name += ext

                if not self._matches_pattern(file_name):
                    continue

                results.append(FileRef(
                    original_path=f"gdrive://{item['id']}",
                    file_name=file_name,
                    file_size_bytes=int(item.get("size", 0)),
                    metadata={
                        "file_id": item["id"],
                        "mime_type": mime,
                    },
                ))

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return results

    def download_files(
        self, files: List[FileRef], staging_dir: str
    ) -> List[StagedFile]:
        os.makedirs(staging_dir, exist_ok=True)
        staged = []

        for f in files:
            file_id = f.metadata["file_id"]
            mime = f.metadata["mime_type"]

            buffer = io.BytesIO()

            if mime in EXPORT_MAP:
                export_mime, _ = EXPORT_MAP[mime]
                request = self._service.files().export_media(
                    fileId=file_id, mimeType=export_mime
                )
            else:
                request = self._service.files().get_media(fileId=file_id)

            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            content = buffer.getvalue()
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
