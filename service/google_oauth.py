"""Google OAuth access tokens for the read-only Drive importer.

The importer historically relied on ``GOOGLE_DRIVE_ACCESS_TOKEN``, a short-lived
token that has to be pasted in by hand and expires mid-import. When a refresh
token is configured this module mints access tokens on demand instead, caching
them in memory until shortly before Google says they expire.

Nothing in here ever logs or formats a client secret, a refresh token or an
access token: failures are reported with the HTTP status and Google's own error
code, both of which are safe to surface to operators.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable


GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

# Refresh this many seconds before the advertised expiry so an in-flight Drive
# call never races the expiry boundary.
TOKEN_EXPIRY_SKEW_SECONDS = 120
# Google always returns expires_in; this only guards a malformed response.
DEFAULT_TOKEN_TTL_SECONDS = 3600
TOKEN_REQUEST_TIMEOUT_SECONDS = 30

CLIENT_ID_ENV = "GOOGLE_DRIVE_CLIENT_ID"
CLIENT_SECRET_ENV = "GOOGLE_DRIVE_CLIENT_SECRET"
REFRESH_TOKEN_ENV = "GOOGLE_DRIVE_REFRESH_TOKEN"
_OAUTH_ENV_VARS = (CLIENT_ID_ENV, CLIENT_SECRET_ENV, REFRESH_TOKEN_ENV)

logger = logging.getLogger("cv_pipeline.google_oauth")


class GoogleOAuthError(RuntimeError):
    """Raised when a Google access token cannot be obtained."""


@dataclass(frozen=True)
class GoogleOAuthConfig:
    """A complete installed-app refresh-token credential."""

    client_id: str
    client_secret: str
    refresh_token: str

    @property
    def cache_key(self) -> tuple[str, int, int]:
        """Identify the credential without keeping its secrets comparable.

        The client id is not a secret; the secret and refresh token are reduced
        to hashes so rotating a credential invalidates the cached access token
        without the raw values being stored a second time.
        """
        return (self.client_id, hash(self.client_secret), hash(self.refresh_token))


def load_oauth_config(env: dict[str, str] | None = None) -> GoogleOAuthConfig | None:
    """Read the refresh-token credential from the environment.

    Returns ``None`` when no OAuth variable is set at all, so the caller can fall
    back to the legacy static-token configuration. Raises when the credential is
    only partially configured: that is always an operator mistake, and silently
    falling back would reintroduce the expiring-token failure we are removing.
    """
    source = os.environ if env is None else env
    values = {name: (source.get(name) or "").strip() for name in _OAUTH_ENV_VARS}

    present = [name for name, value in values.items() if value]
    if not present:
        return None

    missing = [name for name, value in values.items() if not value]
    if missing:
        raise GoogleOAuthError(
            "Google Drive OAuth configuration is incomplete. Set "
            + ", ".join(missing)
            + " (or clear "
            + ", ".join(present)
            + " to fall back to GOOGLE_DRIVE_ACCESS_TOKEN)."
        )

    return GoogleOAuthConfig(
        client_id=values[CLIENT_ID_ENV],
        client_secret=values[CLIENT_SECRET_ENV],
        refresh_token=values[REFRESH_TOKEN_ENV],
    )


class GoogleOAuthTokenProvider:
    """Caches one access token per credential, refreshing it near expiry."""

    def __init__(
        self,
        *,
        token_endpoint: str = GOOGLE_TOKEN_ENDPOINT,
        expiry_skew_seconds: float = TOKEN_EXPIRY_SKEW_SECONDS,
        timeout_seconds: float = TOKEN_REQUEST_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._token_endpoint = token_endpoint
        self._expiry_skew_seconds = expiry_skew_seconds
        self._timeout_seconds = timeout_seconds
        # Monotonic by default: a host clock adjustment must not extend a
        # token's life. Injectable so tests can travel past an expiry.
        self._clock = clock
        self._lock = threading.Lock()
        self._cached_token: str | None = None
        self._cached_key: tuple[str, int, int] | None = None
        self._expires_at: float = 0.0

    def get_access_token(self, config: GoogleOAuthConfig) -> str:
        """Return a valid access token, refreshing it only when required."""
        cache_key = config.cache_key
        with self._lock:
            if (
                self._cached_token is not None
                and self._cached_key == cache_key
                and self._clock() < self._expires_at
            ):
                return self._cached_token

            token, ttl_seconds = self._request_access_token(config)
            self._cached_token = token
            self._cached_key = cache_key
            self._expires_at = self._clock() + max(
                0.0, ttl_seconds - self._expiry_skew_seconds
            )
            logger.info(
                "Google Drive OAuth access token refreshed expires_in=%ss skew=%ss",
                int(ttl_seconds),
                int(self._expiry_skew_seconds),
            )
            return token

    def invalidate(self) -> None:
        """Drop the cached token, e.g. after Drive rejects it with a 401."""
        with self._lock:
            self._cached_token = None
            self._cached_key = None
            self._expires_at = 0.0

    def _request_access_token(self, config: GoogleOAuthConfig) -> tuple[str, float]:
        payload = urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "refresh_token": config.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._token_endpoint,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            reason = _describe_token_error(exc)
            logger.warning(
                "Google Drive OAuth token refresh rejected status=%s reason=%s",
                exc.code,
                reason,
            )
            raise GoogleOAuthError(
                f"Google Drive OAuth token refresh failed with HTTP {exc.code} ({reason}). "
                f"Check {CLIENT_ID_ENV}, {CLIENT_SECRET_ENV} and {REFRESH_TOKEN_ENV}."
            ) from exc
        except OSError as exc:
            logger.warning(
                "Google Drive OAuth token endpoint unreachable error=%s",
                type(exc).__name__,
            )
            raise GoogleOAuthError(
                f"Google Drive OAuth token endpoint is unreachable ({type(exc).__name__})."
            ) from exc

        try:
            data = json.loads(body)
        except ValueError as exc:
            raise GoogleOAuthError(
                "Google Drive OAuth token endpoint returned a malformed response."
            ) from exc

        token = (data.get("access_token") or "").strip() if isinstance(data, dict) else ""
        if not token:
            raise GoogleOAuthError(
                "Google Drive OAuth token endpoint returned no access token."
            )

        try:
            ttl_seconds = float(data.get("expires_in", DEFAULT_TOKEN_TTL_SECONDS))
        except (TypeError, ValueError):
            ttl_seconds = float(DEFAULT_TOKEN_TTL_SECONDS)

        return token, ttl_seconds


def _describe_token_error(exc: urllib.error.HTTPError) -> str:
    """Extract Google's OAuth error code, which never contains a credential."""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 - diagnostics must never mask the HTTP error
        return "unknown_error"

    if not isinstance(data, dict):
        return "unknown_error"

    code = data.get("error")
    if isinstance(code, dict):  # Some Google APIs nest the error object.
        code = code.get("status") or code.get("message")
    if not isinstance(code, str) or not code.strip():
        return "unknown_error"

    # Google's OAuth error codes are short snake_case identifiers; refuse
    # anything else rather than risk echoing an unexpected response body.
    cleaned = code.strip()
    if len(cleaned) > 64 or not all(ch.isalnum() or ch in "_-." for ch in cleaned):
        return "unknown_error"
    return cleaned


_PROVIDER = GoogleOAuthTokenProvider()


def get_access_token() -> str | None:
    """Return a Drive access token minted from the configured refresh token.

    ``None`` means no OAuth credential is configured and the caller should use
    its legacy static-token path.
    """
    config = load_oauth_config()
    if config is None:
        return None
    return _PROVIDER.get_access_token(config)


def reset_token_cache() -> None:
    """Forget the cached access token (used by tests and credential rotation)."""
    _PROVIDER.invalidate()
