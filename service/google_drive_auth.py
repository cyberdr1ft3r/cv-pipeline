"""Google Drive authentication for the CV importer.

Production authenticates with a Google service account that holds Viewer access
to the Shared Drive. The importer previously relied on GOOGLE_DRIVE_ACCESS_TOKEN,
a hand-pasted credential that Google expires after an hour, which repeatedly cut
long imports short. A service-account key can mint fresh access tokens forever,
so the importer prefers it whenever GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE points at a
readable key file.

Credentials and the access token derived from them are cached in memory for the
life of the process, keyed on the key file's identity and mtime, so a Drive run
performs one token exchange rather than one per API call, and rotating the
mounted key file is picked up without a restart.

Nothing here logs or formats a private key, the parsed key file, an access token
or an Authorization header. Errors carry the configured *path*, the exception
*type* and the service-account email - never file contents, and never the
underlying library message, which for a malformed PEM can quote key bytes.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

SERVICE_ACCOUNT_FILE_ENV = "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE"
SHARED_DRIVE_ID_ENV = "GOOGLE_DRIVE_SHARED_DRIVE_ID"
ACCESS_TOKEN_ENV = "GOOGLE_DRIVE_ACCESS_TOKEN"
BEARER_TOKEN_ENV = "GOOGLE_DRIVE_BEARER_TOKEN"

# google-auth treats a token as stale 3m45s before its expiry
# (google.auth._helpers.REFRESH_THRESHOLD). Refresh earlier than that so this
# cache can never hand back a token the library itself considers expired.
TOKEN_EXPIRY_SKEW_SECONDS = 300
# Google always states an expiry; this only guards a credential that omits one.
DEFAULT_TOKEN_TTL_SECONDS = 3600

# The fields google-auth requires of a service-account key file. Checking them
# here turns a library-internal MalformedError into an actionable message.
_REQUIRED_KEY_FIELDS = ("type", "client_email", "token_uri", "private_key")

logger = logging.getLogger("cv_pipeline.google_drive_auth")


class GoogleDriveAuthError(RuntimeError):
    """Raised when Drive credentials cannot be loaded or refreshed."""


def service_account_file() -> str:
    """Path to the mounted service-account key, or "" when not configured."""
    return os.getenv(SERVICE_ACCOUNT_FILE_ENV, "").strip()


def shared_drive_id() -> str:
    """Shared Drive to scope listings to, or "" to keep the default corpora."""
    return os.getenv(SHARED_DRIVE_ID_ENV, "").strip()


def _read_key_file(path: str) -> dict[str, Any]:
    """Parse and sanity-check the key file, mapping every failure to a clear error.

    Runs before google-auth is imported so a misconfigured path reports the real
    problem instead of an ImportError, and so the failure modes stay testable in
    environments where google-auth is not installed.
    """
    # Checked explicitly: opening a directory raises IsADirectoryError on Linux
    # but PermissionError on Windows, which would report the wrong problem.
    if Path(path).is_dir():
        raise GoogleDriveAuthError(
            f"Google Drive service-account key path {path} is a directory, not a key file."
        )

    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file not found at {path}. "
            f"Check the read-only mount and {SERVICE_ACCOUNT_FILE_ENV}."
        ) from exc
    except IsADirectoryError as exc:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key path {path} is a directory, not a key file."
        ) from exc
    except PermissionError as exc:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} is not readable by this "
            "process. Check the file mode and ownership on the mounted secret."
        ) from exc
    except OSError as exc:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} could not be read "
            f"({type(exc).__name__})."
        ) from exc
    except UnicodeDecodeError as exc:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} is not UTF-8 text."
        ) from exc

    try:
        info = json.loads(raw)
    except ValueError as exc:
        # Deliberately not echoing the parser message: it quotes file content.
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} is not valid JSON."
        ) from exc

    if not isinstance(info, dict):
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} is not a JSON object."
        )

    missing = [field for field in _REQUIRED_KEY_FIELDS if not info.get(field)]
    if missing:
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} is missing required "
            f"field(s): {', '.join(missing)}. Export a service-account key in JSON "
            "format from the Google Cloud console."
        )

    if info.get("type") != "service_account":
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} has type "
            f"{info.get('type')!r}; expected 'service_account'."
        )

    return info


def _load_credentials(path: str, scopes: tuple[str, ...]):
    """Build google-auth service-account credentials for the given key file.

    Imported lazily so the importer module stays importable (and testable) in
    environments where google-auth is not installed.
    """
    info = _read_key_file(path)

    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise GoogleDriveAuthError(
            "google-auth is required for Google Drive service-account "
            "authentication but is not installed. Install the pinned "
            "google-auth from service/requirements.txt."
        ) from exc

    try:
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=list(scopes)
        )
    except Exception as exc:  # noqa: BLE001 - message may quote key material
        raise GoogleDriveAuthError(
            f"Google Drive service-account key file at {path} could not be loaded "
            f"({type(exc).__name__}). The private_key entry is most likely corrupt "
            "or truncated."
        ) from exc

    logger.info(
        "Google Drive service-account credentials loaded account=%s scope=%s",
        getattr(credentials, "service_account_email", "unknown"),
        ",".join(scopes),
    )
    return credentials


def _transport_request():
    """Build the HTTP transport google-auth uses for the token exchange."""
    try:
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise GoogleDriveAuthError(
            "google-auth's requests transport is unavailable. Install the pinned "
            "google-auth and requests from service/requirements.txt."
        ) from exc
    return Request()


def _remaining_seconds(credentials) -> float:
    """Seconds until the freshly minted token expires, per google-auth."""
    expiry = getattr(credentials, "expiry", None)
    if not isinstance(expiry, datetime):
        return float(DEFAULT_TOKEN_TTL_SECONDS)

    if expiry.tzinfo is None:
        # google-auth stores a naive UTC expiry.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        now = datetime.now(timezone.utc)
    return (expiry - now).total_seconds()


def _key_file_fingerprint(path: str) -> tuple[str, int, int]:
    """Identify the key file so a rotated mount invalidates the cache."""
    try:
        stat = os.stat(path)
    except OSError:
        # Let _read_key_file produce the actionable error a moment later.
        return (path, -1, -1)
    return (path, stat.st_mtime_ns, stat.st_size)


class ServiceAccountTokenProvider:
    """Caches service-account credentials and the access token they mint."""

    def __init__(
        self,
        *,
        scopes: tuple[str, ...] = (DRIVE_READONLY_SCOPE,),
        expiry_skew_seconds: float = TOKEN_EXPIRY_SKEW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        loader: Callable[[str, tuple[str, ...]], Any] | None = None,
    ) -> None:
        self._scopes = scopes
        self._expiry_skew_seconds = expiry_skew_seconds
        # Monotonic by default: a host clock adjustment must not extend the
        # lifetime this cache believes a token has.
        self._clock = clock
        # Resolved per call rather than bound here so the module-level loader
        # stays patchable for tests that drive the shared provider.
        self._loader = loader
        self._lock = threading.Lock()
        self._credentials = None
        self._credentials_key: tuple[str, int, int] | None = None
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self, credentials_path: str) -> str:
        """Return a valid access token, exchanging only when required."""
        fingerprint = _key_file_fingerprint(credentials_path)
        with self._lock:
            if (
                self._token is not None
                and self._credentials_key == fingerprint
                and self._clock() < self._expires_at
            ):
                return self._token

            if self._credentials is None or self._credentials_key != fingerprint:
                loader = self._loader or _load_credentials
                self._credentials = loader(credentials_path, self._scopes)
                self._credentials_key = fingerprint
                self._token = None
                self._expires_at = 0.0

            self._refresh(self._credentials)
            return self._token

    def invalidate(self) -> None:
        """Forget cached credentials and token (rotation, or a Drive 401)."""
        with self._lock:
            self._credentials = None
            self._credentials_key = None
            self._token = None
            self._expires_at = 0.0

    def _refresh(self, credentials) -> None:
        request = _transport_request()
        try:
            credentials.refresh(request)
        except Exception as exc:  # noqa: BLE001 - library message may echo a body
            account = getattr(credentials, "service_account_email", "unknown")
            logger.warning(
                "Google Drive access token request refused account=%s error=%s",
                account,
                type(exc).__name__,
            )
            raise GoogleDriveAuthError(
                f"Google refused an access token for service account {account} "
                f"({type(exc).__name__}). Confirm the key is active and that the "
                "account still has access to the Shared Drive."
            ) from exc

        token = (getattr(credentials, "token", None) or "").strip()
        if not token:
            raise GoogleDriveAuthError(
                "Google returned no access token for the configured service account."
            )

        ttl_seconds = _remaining_seconds(credentials)
        self._token = token
        self._expires_at = self._clock() + max(
            0.0, ttl_seconds - self._expiry_skew_seconds
        )
        logger.info(
            "Google Drive access token refreshed account=%s expires_in=%ss skew=%ss",
            getattr(credentials, "service_account_email", "unknown"),
            int(ttl_seconds),
            int(self._expiry_skew_seconds),
        )


_PROVIDER = ServiceAccountTokenProvider()


def get_access_token() -> str | None:
    """Return a service-account access token, or None when none is configured.

    ``None`` tells the caller to fall back to the legacy static-token variables.
    """
    path = service_account_file()
    if not path:
        return None
    return _PROVIDER.get_access_token(path)


def reset_credentials_cache() -> None:
    """Drop cached credentials and token (used by tests and key rotation)."""
    _PROVIDER.invalidate()
