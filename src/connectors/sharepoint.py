"""
SharePoint connector: lists and downloads files from SharePoint Online
via Microsoft Graph API using MSAL client-credentials flow.

Required secrets in the configured secret scope:
  - tenant_id_key:    Azure AD tenant ID
  - client_id_key:    App registration client ID
  - client_secret_key: App registration client secret

The app registration needs the Microsoft Graph application permission
Files.Read.All (or Sites.Read.All) with admin consent.
"""

import os
import json
from typing import List

import msal
import requests

from src.connectors import register
from src.connectors.base import BaseConnector, FileRef, StagedFile

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@register("sharepoint")
class SharePointConnector(BaseConnector):

    def __init__(self, source_config: dict, dbutils=None):
        super().__init__(source_config, dbutils=dbutils)
        auth_cfg = source_config.get("auth", {})
        scope = auth_cfg.get("secret_scope", "")
        self._tenant_id = self._get_secret(scope, auth_cfg.get("tenant_id_key", "tenant-id"))
        self._client_id = self._get_secret(scope, auth_cfg.get("client_id_key", "client-id"))
        self._client_secret = self._get_secret(scope, auth_cfg.get("client_secret_key", "client-secret"))
        self._access_token = self._acquire_token()

        self._site_url = source_config.get("site_url", "")
        self._library = source_config.get("library", "Shared Documents")
        single_folder = source_config.get("folder", "/").strip("/")
        self._folders = [f.strip("/") for f in (source_config.get("folders") or [])]
        if single_folder and single_folder != "/":
            self._folders.append(single_folder)
        if not self._folders:
            self._folders = [""]

    def _acquire_token(self) -> str:
        authority = f"https://login.microsoftonline.com/{self._tenant_id}"
        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=authority,
            client_credential=self._client_secret,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise RuntimeError(f"SharePoint auth failed: {result.get('error_description', result)}")
        return result["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _get_site_id(self) -> str:
        """Resolve site URL to a Graph site ID."""
        from urllib.parse import urlparse
        parsed = urlparse(self._site_url)
        hostname = parsed.hostname
        site_path = parsed.path.rstrip("/")
        url = f"{GRAPH_BASE}/sites/{hostname}:{site_path}"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()["id"]

    def _get_drive_id(self, site_id: str) -> str:
        """Find the drive (document library) by display name."""
        url = f"{GRAPH_BASE}/sites/{site_id}/drives"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        for drive in resp.json().get("value", []):
            if drive.get("name") == self._library:
                return drive["id"]
        raise ValueError(f"Document library '{self._library}' not found on site")

    def list_files(self) -> List[FileRef]:
        site_id = self._get_site_id()
        drive_id = self._get_drive_id(site_id)
        results = []
        for folder in self._folders:
            results.extend(self._list_folder(drive_id, folder))
        return results

    def _list_folder(self, drive_id: str, folder_path: str) -> List[FileRef]:
        results = []
        if folder_path:
            url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{folder_path}:/children"
        else:
            url = f"{GRAPH_BASE}/drives/{drive_id}/root/children"

        while url:
            resp = requests.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("value", []):
                if "folder" in item:
                    if self.recursive:
                        child_path = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                        results.extend(self._list_folder(drive_id, child_path))
                elif "file" in item:
                    if self._matches_pattern(item["name"]):
                        results.append(FileRef(
                            original_path=item.get("@microsoft.graph.downloadUrl", item["id"]),
                            file_name=item["name"],
                            file_size_bytes=item.get("size", 0),
                            metadata={
                                "drive_id": drive_id,
                                "item_id": item["id"],
                                "sp_path": f"{folder_path}/{item['name']}",
                            },
                        ))

            url = data.get("@odata.nextLink")

        return results

    def download_files(
        self, files: List[FileRef], staging_dir: str
    ) -> List[StagedFile]:
        os.makedirs(staging_dir, exist_ok=True)
        staged = []

        for f in files:
            drive_id = f.metadata.get("drive_id", "")
            item_id = f.metadata.get("item_id", "")
            download_url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content"

            resp = requests.get(download_url, headers=self._headers(), stream=True)
            resp.raise_for_status()

            content = resp.content
            dest = os.path.join(staging_dir, f.file_name)

            # Avoid name collisions by appending a hash suffix
            if os.path.exists(dest):
                name, ext = os.path.splitext(f.file_name)
                short_hash = self._compute_hash(content)[:8]
                dest = os.path.join(staging_dir, f"{name}_{short_hash}{ext}")

            with open(dest, "wb") as out:
                out.write(content)

            staged.append(StagedFile(
                original_path=f.metadata.get("sp_path", f.original_path),
                staging_path=dest,
                file_name=os.path.basename(dest),
                file_size_bytes=len(content),
                content_hash=self._compute_hash(content),
            ))

        return staged
