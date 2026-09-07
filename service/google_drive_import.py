from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable


DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_FILE_RE = re.compile(r"/file/d/([^/]+)")
DRIVE_FOLDER_RE = re.compile(r"/folders/([^/?#]+)")
DRIVE_OPEN_ID_RE = re.compile(r"[?&]id=([^&#]+)")


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
    query = (
        f"'{folder_id}' in parents and trashed = false and "
        "("
        "mimeType = 'application/pdf' or "
        "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
        "mimeType = 'application/msword'"
        ")"
    )
    params = {
        "q": query,
        "pageSize": str(max(1, min(max_files, 100))),
        "fields": "files(id,name,mimeType,size,webViewLink)",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    data = _drive_json("/files", params)
    return [
        DriveFile(
            file_id=item["id"],
            name=item.get("name") or f"{item['id']}.pdf",
            mime_type=item.get("mimeType") or "",
            size=int(item["size"]) if item.get("size") else None,
            web_url=item.get("webViewLink"),
        )
        for item in data.get("files", [])
    ]


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
                "Google Drive access denied. Set GOOGLE_DRIVE_ACCESS_TOKEN for private files "
                "or GOOGLE_DRIVE_API_KEY for public/shared files."
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
    token = (
        os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip()
        or os.getenv("GOOGLE_DRIVE_BEARER_TOKEN", "").strip()
    )
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
