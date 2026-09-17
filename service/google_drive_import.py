from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Iterable

from service import google_oauth


DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_FILE_RE = re.compile(r"/file/d/([^/]+)")
DRIVE_FOLDER_RE = re.compile(r"/folders/([^/?#]+)")
DRIVE_OPEN_ID_RE = re.compile(r"[?&]id=([^&#]+)")
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
SUPPORTED_FILE_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
)
MAX_FOLDER_SCAN = 1000


class GoogleDriveImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    mime_type: str
    size: int | None = None
    web_url: str | None = None


def extract_drive_id(url_or_id: str, *, folder: bool = False) -> str:
    value = (url_or_id or "").strip()
    if not value:
        raise GoogleDriveImportError("Google Drive URL is empty.")
    if "/" not in value and "?" not in value:
        return value

    pattern = DRIVE_FOLDER_RE if folder else DRIVE_FILE_RE
    match = pattern.search(value)
    if match:
        return urllib.parse.unquote(match.group(1))

    match = DRIVE_OPEN_ID_RE.search(value)
    if match:
        return urllib.parse.unquote(match.group(1))

    kind = "folder" if folder else "file"
    raise GoogleDriveImportError(f"Could not extract Google Drive {kind} id from URL.")


def list_folder_files(folder_url_or_id: str, *, max_files: int = 50) -> list[DriveFile]:
    folder_id = extract_drive_id(folder_url_or_id, folder=True)
    limit = max(1, min(max_files, 100))

    pending = deque([folder_id])
    queued_folders = {folder_id}
    seen_folders: set[str] = set()
    seen_files: set[str] = set()
    result: list[DriveFile] = []

    while pending and len(result) < limit:
        current_folder = pending.popleft()
        if current_folder in seen_folders:
            continue

        seen_folders.add(current_folder)
        if len(seen_folders) > MAX_FOLDER_SCAN:
            raise GoogleDriveImportError(
                "Google Drive folder tree is too large to scan safely."
            )

        page_token: str | None = None
        while len(result) < limit:
            params = {
                "q": f"'{current_folder}' in parents and trashed = false",
                "pageSize": "100",
                "fields": "nextPageToken,files(id,name,mimeType,size,webViewLink)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                params["pageToken"] = page_token

            data = _drive_json("/files", params)
            for item in data.get("files", []):
                item_id = item.get("id")
                mime_type = item.get("mimeType") or ""
                if not item_id:
                    continue

                if mime_type == DRIVE_FOLDER_MIME:
                    if item_id not in queued_folders:
                        queued_folders.add(item_id)
                        pending.append(item_id)
                    continue

                if mime_type not in SUPPORTED_FILE_MIME_TYPES or item_id in seen_files:
                    continue

                seen_files.add(item_id)
                result.append(
                    DriveFile(
                        file_id=item_id,
                        name=item.get("name") or f"{item_id}.pdf",
                        mime_type=mime_type,
                        size=int(item["size"]) if item.get("size") else None,
                        web_url=item.get("webViewLink"),
                    )
                )
                if len(result) >= limit:
                    break

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return result


def get_file_metadata(file_url_or_id: str) -> DriveFile:
    file_id = extract_drive_id(file_url_or_id)
    data = _drive_json(
        f"/files/{urllib.parse.quote(file_id)}",
        {
            "fields": "id,name,mimeType,size,webViewLink",
            "supportsAllDrives": "true",
        },
    )
    return DriveFile(
        file_id=data["id"],
        name=data.get("name") or f"{file_id}.pdf",
        mime_type=data.get("mimeType") or "",
        size=int(data["size"]) if data.get("size") else None,
        web_url=data.get("webViewLink"),
    )


def download_file(file_id: str, *, max_bytes: int) -> bytes:
    params = {"alt": "media", "supportsAllDrives": "true"}
    url = _api_url(f"/files/{urllib.parse.quote(file_id)}", params)
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise GoogleDriveImportError("Google Drive credentials cannot access this file.") from exc
        raise GoogleDriveImportError(f"Google Drive download failed with HTTP {exc.code}.") from exc
    except OSError as exc:
        raise GoogleDriveImportError(f"Google Drive download failed: {exc}") from exc

    if len(content) > max_bytes:
        raise GoogleDriveImportError("Google Drive file exceeds the configured CV upload limit.")
    return content


def dedupe_files(files: Iterable[DriveFile]) -> list[DriveFile]:
    seen: set[str] = set()
    result: list[DriveFile] = []
    for item in files:
        if item.file_id in seen:
            continue
        seen.add(item.file_id)
        result.append(item)
    return result


def _drive_json(path: str, params: dict[str, str]) -> dict:
    url = _api_url(path, params)
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise GoogleDriveImportError(
                "Google Drive access denied. Configure GOOGLE_DRIVE_CLIENT_ID, "
                "GOOGLE_DRIVE_CLIENT_SECRET and GOOGLE_DRIVE_REFRESH_TOKEN for private "
                "files and Shared Drives, or GOOGLE_DRIVE_API_KEY for public files."
            ) from exc
        raise GoogleDriveImportError(f"Google Drive API failed with HTTP {exc.code}.") from exc
    except OSError as exc:
        raise GoogleDriveImportError(f"Google Drive API request failed: {exc}") from exc


def _api_url(path: str, params: dict[str, str]) -> str:
    api_key = os.getenv("GOOGLE_DRIVE_API_KEY", "").strip()
    if api_key and "key" not in params:
        params = {**params, "key": api_key}
    return f"{DRIVE_API_BASE}{path}?{urllib.parse.urlencode(params)}"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = _access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _access_token() -> str:
    """Resolve the bearer token for a Drive call.

    A refresh-token credential wins when one is configured, because it survives
    the one-hour access-token lifetime that kept interrupting bulk imports. The
    hand-pasted GOOGLE_DRIVE_ACCESS_TOKEN / GOOGLE_DRIVE_BEARER_TOKEN variables
    stay supported for deployments that have not been migrated yet.
    """
    try:
        token = google_oauth.get_access_token()
    except google_oauth.GoogleOAuthError as exc:
        # str(exc) is built from the env var names, the HTTP status and Google's
        # error code only - it never carries a credential.
        raise GoogleDriveImportError(str(exc)) from exc

    if token:
        return token

    return (
        os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip()
        or os.getenv("GOOGLE_DRIVE_BEARER_TOKEN", "").strip()
    )
