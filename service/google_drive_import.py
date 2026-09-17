from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from service import google_drive_auth


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

logger = logging.getLogger("cv_pipeline.google_drive_import")

_T = TypeVar("_T")


class GoogleDriveImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    mime_type: str
    size: int | None = None
    web_url: str | None = None
    modified_time: str | None = None
    md5_checksum: str | None = None


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
            # Scoping the corpus to one Shared Drive is what Google recommends for
            # a service account, which has no My Drive of its own. Off by default
            # so an unconfigured deployment keeps today's allDrives behaviour.
            drive_id = google_drive_auth.shared_drive_id()
            if drive_id:
                params["corpora"] = "drive"
                params["driveId"] = drive_id
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


def list_shared_drive_files(drive_id: str | None = None) -> list[DriveFile]:
    """Inventory every supported CV in a Shared Drive without interactive caps."""
    shared_drive = (drive_id or google_drive_auth.shared_drive_id()).strip()
    if not shared_drive:
        raise GoogleDriveImportError(
            "GOOGLE_DRIVE_SHARED_DRIVE_ID is required for bulk inventory."
        )

    mime_query = " or ".join(
        f"mimeType = '{mime_type}'"
        for mime_type in sorted(SUPPORTED_FILE_MIME_TYPES)
    )
    seen_ids: set[str] = set()
    result: list[DriveFile] = []
    page_token: str | None = None

    while True:
        params = {
            "q": f"trashed = false and ({mime_query})",
            "corpora": "drive",
            "driveId": shared_drive,
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "spaces": "drive",
            "pageSize": "1000",
            "fields": (
                "nextPageToken,"
                "files(id,name,mimeType,size,modifiedTime,md5Checksum,webViewLink)"
            ),
        }
        if page_token:
            params["pageToken"] = page_token

        data = _drive_json("/files", params)
        for item in data.get("files", []):
            file_id = item.get("id")
            mime_type = item.get("mimeType") or ""
            if (
                not file_id
                or file_id in seen_ids
                or mime_type not in SUPPORTED_FILE_MIME_TYPES
            ):
                continue
            seen_ids.add(file_id)
            result.append(
                DriveFile(
                    file_id=file_id,
                    name=item.get("name") or file_id,
                    mime_type=mime_type,
                    size=int(item["size"]) if item.get("size") else None,
                    web_url=item.get("webViewLink"),
                    modified_time=item.get("modifiedTime"),
                    md5_checksum=item.get("md5Checksum"),
                )
            )

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

    def perform() -> bytes:
        request = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read(max_bytes + 1)

    try:
        content = _retry_once_on_expired_token(perform)
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

    def perform() -> dict:
        request = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        return _retry_once_on_expired_token(perform)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise GoogleDriveImportError(
                "Google Drive access denied. Point GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE at a "
                "service-account key with Viewer access to the Shared Drive, or set "
                "GOOGLE_DRIVE_API_KEY for public files."
            ) from exc
        raise GoogleDriveImportError(f"Google Drive API failed with HTTP {exc.code}.") from exc
    except OSError as exc:
        raise GoogleDriveImportError(f"Google Drive API request failed: {exc}") from exc


def _retry_once_on_expired_token(perform: Callable[[], _T]) -> _T:
    """Run a Drive call, retrying once with a freshly minted token on HTTP 401.

    Only service-account authentication is retried, and only on 401. A cached
    access token that Google has stopped accepting would otherwise keep being
    replayed until the local cache expires, which with a one-hour token is up to
    55 minutes of failing imports.

    403 is deliberately excluded: it means the account lacks permission on the
    file or the Shared Drive, and a fresh token would be rejected identically.
    The legacy static-token path is excluded too - there is nothing to re-mint,
    so a retry would just double every failing request.
    """
    try:
        return perform()
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or not google_drive_auth.service_account_file():
            raise

    # Exactly one retry: a second 401 propagates to the caller's handler.
    logger.info(
        "Google Drive rejected the cached service-account token (HTTP 401); "
        "refreshing once and retrying the request"
    )
    google_drive_auth.reset_credentials_cache()
    return perform()


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

    A service-account key wins whenever one is configured, because it mints
    fresh tokens indefinitely instead of expiring mid-import. The hand-pasted
    GOOGLE_DRIVE_ACCESS_TOKEN / GOOGLE_DRIVE_BEARER_TOKEN variables stay
    supported for deployments that have not been migrated yet.
    """
    try:
        token = google_drive_auth.get_access_token()
    except google_drive_auth.GoogleDriveAuthError as exc:
        # str(exc) is built from the configured path, the exception type and the
        # service-account email - it never carries key material or a token.
        raise GoogleDriveImportError(str(exc)) from exc

    if token:
        return token

    return (
        os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip()
        or os.getenv("GOOGLE_DRIVE_BEARER_TOKEN", "").strip()
    )
