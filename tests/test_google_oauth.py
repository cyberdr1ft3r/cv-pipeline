"""Tests for the Google Drive OAuth refresh-token provider.

Every HTTP boundary is mocked: no test in this module may reach Google. The
``setUp`` guard replaces ``urllib.request.urlopen`` with a fail-fast stub so an
unmocked call is a test failure rather than a silent network request.
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
import urllib.parse
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from service import google_drive_import, google_oauth
from service.google_oauth import (
    GoogleOAuthConfig,
    GoogleOAuthError,
    GoogleOAuthTokenProvider,
    load_oauth_config,
)


CLIENT_ID = "sentinel-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "sentinel-client-secret-SHOULD-NEVER-BE-LOGGED"
REFRESH_TOKEN = "sentinel-refresh-token-SHOULD-NEVER-BE-LOGGED"
ACCESS_TOKEN = "sentinel-access-token-SHOULD-NEVER-BE-LOGGED"
SECRETS = (CLIENT_SECRET, REFRESH_TOKEN, ACCESS_TOKEN)

DRIVE_ENV_VARS = (
    "GOOGLE_DRIVE_CLIENT_ID",
    "GOOGLE_DRIVE_CLIENT_SECRET",
    "GOOGLE_DRIVE_REFRESH_TOKEN",
    "GOOGLE_DRIVE_ACCESS_TOKEN",
    "GOOGLE_DRIVE_BEARER_TOKEN",
    "GOOGLE_DRIVE_API_KEY",
)

CONFIG = GoogleOAuthConfig(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
)


@contextmanager
def drive_env(**overrides: str):
    """Run with a known-clean set of GOOGLE_DRIVE_* variables."""
    env = {name: os.environ[name] for name in os.environ}
    for name in DRIVE_ENV_VARS:
        env.pop(name, None)
    env.update(overrides)
    with patch.dict(os.environ, env, clear=True):
        yield


def json_response(payload: dict) -> MagicMock:
    """Build a urlopen return value usable as a context manager."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    opened = MagicMock()
    opened.__enter__.return_value = response
    opened.__exit__.return_value = False
    return opened


def http_error(status: int, payload: object) -> urllib.error.HTTPError:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return urllib.error.HTTPError(
        "https://oauth2.googleapis.com/token",
        status,
        "Bad Request",
        {},
        io.BytesIO(body),
    )


def token_payload(access_token: str = ACCESS_TOKEN, expires_in: int = 3599) -> dict:
    return {
        "access_token": access_token,
        "expires_in": expires_in,
        "scope": google_oauth.DRIVE_READONLY_SCOPE,
        "token_type": "Bearer",
    }


def posted_form(urlopen: MagicMock, call_index: int = 0) -> dict[str, list[str]]:
    request = urlopen.call_args_list[call_index].args[0]
    return urllib.parse.parse_qs(request.data.decode("utf-8"))


class NoNetworkTestCase(unittest.TestCase):
    """Base case that fails loudly if a test forgets to mock urlopen."""

    def setUp(self) -> None:
        def forbidden(*args, **kwargs):
            raise AssertionError("tests must not perform real HTTP requests")

        guard = patch("urllib.request.urlopen", side_effect=forbidden)
        guard.start()
        self.addCleanup(guard.stop)
        self.addCleanup(google_oauth.reset_token_cache)


class TokenRefreshTests(NoNetworkTestCase):
    def test_refresh_exchanges_refresh_token_at_googles_token_endpoint(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response(token_payload())
            token = provider.get_access_token(CONFIG)

        self.assertEqual(token, ACCESS_TOKEN)
        urlopen.assert_called_once()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, google_oauth.GOOGLE_TOKEN_ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.headers["Content-type"], "application/x-www-form-urlencoded"
        )

        form = posted_form(urlopen)
        self.assertEqual(form["grant_type"], ["refresh_token"])
        self.assertEqual(form["client_id"], [CLIENT_ID])
        self.assertEqual(form["client_secret"], [CLIENT_SECRET])
        self.assertEqual(form["refresh_token"], [REFRESH_TOKEN])

    def test_cached_token_is_reused_until_it_nears_expiry(self) -> None:
        now = [0.0]
        provider = GoogleOAuthTokenProvider(clock=lambda: now[0])

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response(token_payload(expires_in=3600))

            first = provider.get_access_token(CONFIG)
            now[0] = 3600 - google_oauth.TOKEN_EXPIRY_SKEW_SECONDS - 1
            second = provider.get_access_token(CONFIG)

        self.assertEqual(first, ACCESS_TOKEN)
        self.assertEqual(second, ACCESS_TOKEN)
        urlopen.assert_called_once()

    def test_token_is_refreshed_once_the_skew_window_is_reached(self) -> None:
        now = [0.0]
        provider = GoogleOAuthTokenProvider(clock=lambda: now[0])

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                json_response(token_payload("first-token", expires_in=3600)),
                json_response(token_payload("second-token", expires_in=3600)),
            ]

            first = provider.get_access_token(CONFIG)
            # The skew means the refresh happens before Google's stated expiry.
            now[0] = 3600 - google_oauth.TOKEN_EXPIRY_SKEW_SECONDS
            second = provider.get_access_token(CONFIG)

        self.assertEqual(first, "first-token")
        self.assertEqual(second, "second-token")
        self.assertEqual(urlopen.call_count, 2)

    def test_rotated_credentials_invalidate_the_cached_token(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)
        rotated = GoogleOAuthConfig(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token="rotated-refresh-token",
        )

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                json_response(token_payload("old-token")),
                json_response(token_payload("new-token")),
            ]

            self.assertEqual(provider.get_access_token(CONFIG), "old-token")
            self.assertEqual(provider.get_access_token(rotated), "new-token")

        self.assertEqual(urlopen.call_count, 2)

    def test_invalidate_forces_the_next_call_to_refresh(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                json_response(token_payload("first-token")),
                json_response(token_payload("second-token")),
            ]

            self.assertEqual(provider.get_access_token(CONFIG), "first-token")
            provider.invalidate()
            self.assertEqual(provider.get_access_token(CONFIG), "second-token")

    def test_missing_expires_in_falls_back_to_the_default_ttl(self) -> None:
        now = [0.0]
        provider = GoogleOAuthTokenProvider(clock=lambda: now[0])

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response({"access_token": ACCESS_TOKEN})

            provider.get_access_token(CONFIG)
            now[0] = (
                google_oauth.DEFAULT_TOKEN_TTL_SECONDS
                - google_oauth.TOKEN_EXPIRY_SKEW_SECONDS
                - 1
            )
            provider.get_access_token(CONFIG)

        urlopen.assert_called_once()


class TokenFailureTests(NoNetworkTestCase):
    def test_invalid_refresh_token_fails_closed_with_googles_error_code(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = http_error(
                400,
                {
                    "error": "invalid_grant",
                    "error_description": "Token has been expired or revoked.",
                },
            )
            with self.assertRaises(GoogleOAuthError) as caught:
                provider.get_access_token(CONFIG)

        message = str(caught.exception)
        self.assertIn("HTTP 400", message)
        self.assertIn("invalid_grant", message)
        self.assertIn("GOOGLE_DRIVE_REFRESH_TOKEN", message)

    def test_rejected_refresh_is_not_cached(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                http_error(400, {"error": "invalid_grant"}),
                json_response(token_payload()),
            ]

            with self.assertRaises(GoogleOAuthError):
                provider.get_access_token(CONFIG)
            self.assertEqual(provider.get_access_token(CONFIG), ACCESS_TOKEN)

    def test_unexpected_error_body_is_not_echoed_back(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = http_error(
                500, {"error": f"leaked {CLIENT_SECRET} <html>"}
            )
            with self.assertRaises(GoogleOAuthError) as caught:
                provider.get_access_token(CONFIG)

        message = str(caught.exception)
        self.assertIn("unknown_error", message)
        self.assertNotIn(CLIENT_SECRET, message)

    def test_response_without_access_token_is_rejected(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response({"expires_in": 3599})
            with self.assertRaisesRegex(GoogleOAuthError, "no access token"):
                provider.get_access_token(CONFIG)

    def test_malformed_response_is_rejected(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)
        response = MagicMock()
        response.read.return_value = b"<html>not json</html>"
        opened = MagicMock()
        opened.__enter__.return_value = response

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = opened
            with self.assertRaisesRegex(GoogleOAuthError, "malformed response"):
                provider.get_access_token(CONFIG)

    def test_unreachable_token_endpoint_reports_the_error_type_only(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = TimeoutError("timed out")
            with self.assertRaises(GoogleOAuthError) as caught:
                provider.get_access_token(CONFIG)

        self.assertIn("TimeoutError", str(caught.exception))
        self.assertIn("unreachable", str(caught.exception))


class ConfigurationTests(NoNetworkTestCase):
    def test_no_oauth_variables_returns_none_for_legacy_fallback(self) -> None:
        with drive_env():
            self.assertIsNone(load_oauth_config())

    def test_complete_configuration_is_loaded(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=f"  {CLIENT_ID}  ",
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_REFRESH_TOKEN=REFRESH_TOKEN,
        ):
            config = load_oauth_config()

        self.assertIsNotNone(config)
        self.assertEqual(config.client_id, CLIENT_ID)
        self.assertEqual(config.client_secret, CLIENT_SECRET)
        self.assertEqual(config.refresh_token, REFRESH_TOKEN)

    def test_incomplete_configuration_names_the_missing_variables(self) -> None:
        with drive_env(GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID):
            with self.assertRaises(GoogleOAuthError) as caught:
                load_oauth_config()

        message = str(caught.exception)
        self.assertIn("GOOGLE_DRIVE_CLIENT_SECRET", message)
        self.assertIn("GOOGLE_DRIVE_REFRESH_TOKEN", message)
        self.assertIn("GOOGLE_DRIVE_CLIENT_ID", message)

    def test_blank_variables_count_as_unset(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID="   ",
            GOOGLE_DRIVE_CLIENT_SECRET="",
            GOOGLE_DRIVE_REFRESH_TOKEN="\t",
        ):
            self.assertIsNone(load_oauth_config())

    def test_incomplete_configuration_does_not_fall_back_to_static_token(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_ACCESS_TOKEN="legacy-token",
        ):
            with self.assertRaises(google_drive_import.GoogleDriveImportError) as caught:
                google_drive_import._headers()

        self.assertIn("GOOGLE_DRIVE_REFRESH_TOKEN", str(caught.exception))


class DriveAuthenticationTests(NoNetworkTestCase):
    def test_refresh_token_credentials_are_preferred_over_a_static_token(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_REFRESH_TOKEN=REFRESH_TOKEN,
            GOOGLE_DRIVE_ACCESS_TOKEN="stale-pasted-token",
        ):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = json_response(token_payload())
                headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], f"Bearer {ACCESS_TOKEN}")

    def test_static_access_token_still_works_when_oauth_is_unconfigured(self) -> None:
        with drive_env(GOOGLE_DRIVE_ACCESS_TOKEN="legacy-token"):
            headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], "Bearer legacy-token")

    def test_bearer_token_alias_still_works(self) -> None:
        with drive_env(GOOGLE_DRIVE_BEARER_TOKEN="legacy-bearer"):
            headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], "Bearer legacy-bearer")

    def test_no_credentials_sends_no_authorization_header(self) -> None:
        with drive_env():
            headers = google_drive_import._headers()

        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Accept"], "application/json")

    def test_shared_drive_listing_uses_the_refreshed_token(self) -> None:
        drive_page = {
            "files": [
                {
                    "id": "cv-1",
                    "name": "cv.pdf",
                    "mimeType": "application/pdf",
                    "size": "1024",
                }
            ]
        }

        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_REFRESH_TOKEN=REFRESH_TOKEN,
        ):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.side_effect = [
                    json_response(token_payload()),
                    json_response(drive_page),
                ]
                files = google_drive_import.list_folder_files(
                    "https://drive.google.com/drive/folders/0ALDuIiahZzhqUk9PVA",
                    max_files=10,
                )

        self.assertEqual([item.file_id for item in files], ["cv-1"])

        token_request, drive_request = (
            call.args[0] for call in urlopen.call_args_list
        )
        self.assertEqual(token_request.full_url, google_oauth.GOOGLE_TOKEN_ENDPOINT)
        self.assertEqual(
            drive_request.headers["Authorization"], f"Bearer {ACCESS_TOKEN}"
        )

        query = urllib.parse.parse_qs(urllib.parse.urlparse(drive_request.full_url).query)
        self.assertEqual(query["supportsAllDrives"], ["true"])
        self.assertEqual(query["includeItemsFromAllDrives"], ["true"])
        self.assertIn("'0ALDuIiahZzhqUk9PVA' in parents", query["q"][0])

    def test_one_refresh_serves_a_whole_import_run(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_REFRESH_TOKEN=REFRESH_TOKEN,
        ):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = json_response(token_payload())
                first = google_drive_import._headers()
                second = google_drive_import._headers()

        self.assertEqual(first["Authorization"], second["Authorization"])
        urlopen.assert_called_once()


class SecretRedactionTests(NoNetworkTestCase):
    def assert_no_secrets(self, text: str) -> None:
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def test_successful_refresh_logs_nothing_secret(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response(token_payload())
            with self.assertLogs("cv_pipeline.google_oauth", level="DEBUG") as logs:
                provider.get_access_token(CONFIG)

        self.assert_no_secrets("\n".join(logs.output))
        self.assertIn("expires_in=3599", "\n".join(logs.output))

    def test_failed_refresh_logs_and_raises_nothing_secret(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = http_error(
                401,
                {
                    "error": "unauthorized_client",
                    "error_description": f"secret {CLIENT_SECRET} rejected",
                },
            )
            with self.assertLogs("cv_pipeline.google_oauth", level="DEBUG") as logs:
                with self.assertRaises(GoogleOAuthError) as caught:
                    provider.get_access_token(CONFIG)

        self.assert_no_secrets("\n".join(logs.output))
        self.assert_no_secrets(str(caught.exception))
        self.assert_no_secrets(repr(caught.exception))

    def test_incomplete_configuration_error_names_variables_not_values(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
        ):
            with self.assertRaises(GoogleOAuthError) as caught:
                load_oauth_config()

        self.assert_no_secrets(str(caught.exception))

    def test_drive_errors_never_carry_the_authorization_header(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_CLIENT_ID=CLIENT_ID,
            GOOGLE_DRIVE_CLIENT_SECRET=CLIENT_SECRET,
            GOOGLE_DRIVE_REFRESH_TOKEN=REFRESH_TOKEN,
        ):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.side_effect = [
                    json_response(token_payload()),
                    urllib.error.HTTPError(
                        "https://www.googleapis.com/drive/v3/files",
                        403,
                        "Forbidden",
                        {},
                        io.BytesIO(b'{"error": "forbidden"}'),
                    ),
                ]
                with self.assertRaises(
                    google_drive_import.GoogleDriveImportError
                ) as caught:
                    google_drive_import.list_folder_files("folder-id", max_files=1)

        self.assert_no_secrets(str(caught.exception))
        self.assertNotIn("Bearer", str(caught.exception))

    def test_provider_repr_does_not_expose_the_cached_token(self) -> None:
        provider = GoogleOAuthTokenProvider(clock=lambda: 0.0)

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = json_response(token_payload())
            provider.get_access_token(CONFIG)

        self.assert_no_secrets(repr(provider))
        self.assert_no_secrets(repr(vars(provider).get("_cached_key")))


if __name__ == "__main__":
    unittest.main()
