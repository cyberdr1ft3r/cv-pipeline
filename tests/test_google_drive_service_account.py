"""Tests for Google Drive service-account authentication.

No test here may reach Google. The credential loader and the google-auth
transport are both replaced with fakes, and ``NoNetworkTestCase`` swaps
``urllib.request.urlopen`` for a stub that raises, so an unmocked Drive call
fails the test instead of opening a socket.

The fakes mirror the parts of ``google.oauth2.service_account.Credentials`` the
provider actually touches: ``token``, ``expiry``, ``service_account_email`` and
``refresh(request)``.
"""

from __future__ import annotations

import io
import json
import os
import sys
import types
import unittest
import urllib.error
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from service import google_drive_auth, google_drive_import
from service.google_drive_auth import (
    DRIVE_READONLY_SCOPE,
    GoogleDriveAuthError,
    ServiceAccountTokenProvider,
)


SERVICE_ACCOUNT_EMAIL = "workspace-backup@vernal-store-488312-h8.iam.gserviceaccount.com"
SHARED_DRIVE_ID = "0ALDuIiahZzhqUk9PVA"

# Sentinels that must never surface in a log record or an error message.
PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "SENTINEL-PRIVATE-KEY-MATERIAL-SHOULD-NEVER-BE-LOGGED\n"
    "-----END PRIVATE KEY-----\n"
)
ACCESS_TOKEN = "sentinel-access-token-SHOULD-NEVER-BE-LOGGED"
LEGACY_TOKEN = "sentinel-legacy-token-SHOULD-NEVER-BE-LOGGED"
SECRETS = (PRIVATE_KEY, PRIVATE_KEY.strip(), ACCESS_TOKEN)

DRIVE_ENV_VARS = (
    "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE",
    "GOOGLE_DRIVE_SHARED_DRIVE_ID",
    "GOOGLE_DRIVE_ACCESS_TOKEN",
    "GOOGLE_DRIVE_BEARER_TOKEN",
    "GOOGLE_DRIVE_API_KEY",
)


def key_file_contents(**overrides) -> dict:
    info = {
        "type": "service_account",
        "project_id": "vernal-store-488312-h8",
        "private_key_id": "sentinel-key-id",
        "private_key": PRIVATE_KEY,
        "client_email": SERVICE_ACCOUNT_EMAIL,
        "client_id": "000000000000000000000",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    info.update(overrides)
    return info


@contextmanager
def drive_env(**overrides: str):
    """Run with a known-clean set of GOOGLE_DRIVE_* variables."""
    env = dict(os.environ)
    for name in DRIVE_ENV_VARS:
        env.pop(name, None)
    env.update(overrides)
    with patch.dict(os.environ, env, clear=True):
        yield


class FakeCredentials:
    """Stand-in for google-auth service-account credentials."""

    def __init__(self, tokens=("token-1", "token-2", "token-3"), ttl_seconds=3600):
        self._tokens = list(tokens)
        self._ttl_seconds = ttl_seconds
        self.token = None
        self.expiry = None
        self.service_account_email = SERVICE_ACCOUNT_EMAIL
        self.refresh_calls = 0
        self.refresh_error: Exception | None = None

    def refresh(self, request):  # noqa: ARG002 - transport is irrelevant here
        self.refresh_calls += 1
        if self.refresh_error is not None:
            raise self.refresh_error
        self.token = self._tokens.pop(0) if self._tokens else "exhausted-token"
        # google-auth stores a naive UTC expiry.
        self.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=self._ttl_seconds
        )


def json_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    opened = MagicMock()
    opened.__enter__.return_value = response
    opened.__exit__.return_value = False
    return opened


class NoNetworkTestCase(unittest.TestCase):
    def setUp(self) -> None:
        def forbidden(*args, **kwargs):
            raise AssertionError("tests must not perform real HTTP requests")

        guard = patch("urllib.request.urlopen", side_effect=forbidden)
        guard.start()
        self.addCleanup(guard.stop)

        # The google-auth transport is never exercised against a real endpoint.
        transport = patch.object(
            google_drive_auth, "_transport_request", return_value=object()
        )
        transport.start()
        self.addCleanup(transport.stop)

        self.addCleanup(google_drive_auth.reset_credentials_cache)

    def write_key_file(self, contents=None, name="service-account.json") -> str:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / name
        if contents is None:
            contents = json.dumps(key_file_contents())
        path.write_text(contents, encoding="utf-8")
        return str(path)

    def provider(self, credentials=None, clock=None):
        credentials = credentials or FakeCredentials()
        self.loaded: list[tuple[str, tuple[str, ...]]] = []

        def loader(path, scopes):
            self.loaded.append((path, scopes))
            return credentials

        return ServiceAccountTokenProvider(
            clock=clock or (lambda: 0.0), loader=loader
        ), credentials


class CredentialLoadingTests(NoNetworkTestCase):
    def test_key_file_is_loaded_with_the_drive_readonly_scope(self) -> None:
        """The official google-auth entry point is called with the right scope."""
        path = self.write_key_file()
        captured = {}

        class FakeServiceAccountCredentials:
            @staticmethod
            def from_service_account_info(info, scopes):
                captured["info"] = info
                captured["scopes"] = scopes
                return FakeCredentials()

        fake_module = types.ModuleType("google.oauth2.service_account")
        fake_module.Credentials = FakeServiceAccountCredentials

        with patch.dict(
            sys.modules,
            {
                "google": types.ModuleType("google"),
                "google.oauth2": types.ModuleType("google.oauth2"),
                "google.oauth2.service_account": fake_module,
            },
        ):
            credentials = google_drive_auth._load_credentials(
                path, (DRIVE_READONLY_SCOPE,)
            )

        self.assertEqual(captured["scopes"], [DRIVE_READONLY_SCOPE])
        self.assertEqual(captured["info"]["client_email"], SERVICE_ACCOUNT_EMAIL)
        self.assertEqual(credentials.service_account_email, SERVICE_ACCOUNT_EMAIL)

    def test_access_token_is_generated_from_the_credentials(self) -> None:
        provider, credentials = self.provider(FakeCredentials(tokens=[ACCESS_TOKEN]))
        path = self.write_key_file()

        token = provider.get_access_token(path)

        self.assertEqual(token, ACCESS_TOKEN)
        self.assertEqual(credentials.refresh_calls, 1)
        self.assertEqual(self.loaded, [(path, (DRIVE_READONLY_SCOPE,))])

    def test_token_is_reused_while_it_remains_valid(self) -> None:
        now = [0.0]
        provider, credentials = self.provider(clock=lambda: now[0])
        path = self.write_key_file()

        first = provider.get_access_token(path)
        now[0] = 3600 - google_drive_auth.TOKEN_EXPIRY_SKEW_SECONDS - 1
        second = provider.get_access_token(path)

        self.assertEqual(first, "token-1")
        self.assertEqual(second, "token-1")
        self.assertEqual(credentials.refresh_calls, 1)
        self.assertEqual(len(self.loaded), 1)

    def test_token_is_refreshed_once_the_skew_window_is_reached(self) -> None:
        now = [0.0]
        provider, credentials = self.provider(clock=lambda: now[0])
        path = self.write_key_file()

        first = provider.get_access_token(path)
        now[0] = 3600 - google_drive_auth.TOKEN_EXPIRY_SKEW_SECONDS
        second = provider.get_access_token(path)

        self.assertEqual(first, "token-1")
        self.assertEqual(second, "token-2")
        self.assertEqual(credentials.refresh_calls, 2)
        # Credentials are loaded once; only the token is re-minted.
        self.assertEqual(len(self.loaded), 1)

    def test_skew_is_wider_than_google_auths_own_refresh_threshold(self) -> None:
        """Our cache must never outlive what google-auth considers fresh."""
        self.assertGreaterEqual(
            google_drive_auth.TOKEN_EXPIRY_SKEW_SECONDS,
            225,  # google.auth._helpers.REFRESH_THRESHOLD is 3m45s
        )

    def test_rotating_the_key_file_reloads_credentials(self) -> None:
        provider, _ = self.provider()
        path = self.write_key_file()

        provider.get_access_token(path)
        rotated = key_file_contents(private_key_id="rotated-key-id")
        Path(path).write_text(json.dumps(rotated) + "\n", encoding="utf-8")
        provider.get_access_token(path)

        self.assertEqual(len(self.loaded), 2)

    def test_invalidate_forces_a_reload(self) -> None:
        provider, credentials = self.provider()
        path = self.write_key_file()

        provider.get_access_token(path)
        provider.invalidate()
        provider.get_access_token(path)

        self.assertEqual(len(self.loaded), 2)
        self.assertEqual(credentials.refresh_calls, 2)

    def test_credentials_without_an_expiry_use_the_default_ttl(self) -> None:
        now = [0.0]
        credentials = FakeCredentials()
        provider, _ = self.provider(credentials, clock=lambda: now[0])
        path = self.write_key_file()

        provider.get_access_token(path)
        credentials.expiry = None
        now[0] = (
            google_drive_auth.DEFAULT_TOKEN_TTL_SECONDS
            - google_drive_auth.TOKEN_EXPIRY_SKEW_SECONDS
            - 1
        )
        provider.get_access_token(path)

        self.assertEqual(credentials.refresh_calls, 1)


class FailClosedTests(NoNetworkTestCase):
    def real_provider(self) -> ServiceAccountTokenProvider:
        """A provider using the real loader, which validates before importing."""
        return ServiceAccountTokenProvider(clock=lambda: 0.0)

    def test_missing_key_file_fails_with_the_configured_path(self) -> None:
        provider = self.real_provider()
        missing = str(Path(self.write_key_file()).parent / "absent.json")

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(missing)

        message = str(caught.exception)
        self.assertIn("not found", message)
        self.assertIn("absent.json", message)

    def test_directory_instead_of_a_key_file_fails_closed(self) -> None:
        provider = self.real_provider()
        directory = str(Path(self.write_key_file()).parent)

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(directory)

        self.assertIn("is a directory", str(caught.exception))

    def test_invalid_json_fails_without_echoing_file_contents(self) -> None:
        provider = self.real_provider()
        path = self.write_key_file(contents="{ this is not json " + PRIVATE_KEY)

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(path)

        message = str(caught.exception)
        self.assertIn("not valid JSON", message)
        self.assertNotIn(PRIVATE_KEY.strip(), message)

    def test_missing_required_fields_names_them(self) -> None:
        provider = self.real_provider()
        incomplete = key_file_contents()
        del incomplete["client_email"]
        del incomplete["token_uri"]
        path = self.write_key_file(contents=json.dumps(incomplete))

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(path)

        message = str(caught.exception)
        self.assertIn("client_email", message)
        self.assertIn("token_uri", message)
        self.assertNotIn(PRIVATE_KEY.strip(), message)

    def test_wrong_credential_type_is_rejected(self) -> None:
        provider = self.real_provider()
        path = self.write_key_file(
            contents=json.dumps(key_file_contents(type="authorized_user"))
        )

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(path)

        self.assertIn("service_account", str(caught.exception))

    def test_placeholder_credential_file_is_rejected(self) -> None:
        """The committed compose placeholder must never authenticate."""
        placeholder = Path(__file__).resolve().parents[1] / "deploy" / "service-account.placeholder.json"
        provider = self.real_provider()

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(str(placeholder))

        self.assertIn("missing required field", str(caught.exception))

    def test_refused_token_request_fails_closed(self) -> None:
        credentials = FakeCredentials()
        credentials.refresh_error = RuntimeError("RefreshError: invalid_grant")
        provider, _ = self.provider(credentials)
        path = self.write_key_file()

        with self.assertRaises(GoogleDriveAuthError) as caught:
            provider.get_access_token(path)

        message = str(caught.exception)
        self.assertIn(SERVICE_ACCOUNT_EMAIL, message)
        self.assertIn("RuntimeError", message)

    def test_empty_token_response_fails_closed(self) -> None:
        class BlankCredentials(FakeCredentials):
            def refresh(self, request):
                self.refresh_calls += 1
                self.token = ""

        provider, _ = self.provider(BlankCredentials())
        path = self.write_key_file()

        with self.assertRaisesRegex(GoogleDriveAuthError, "no access token"):
            provider.get_access_token(path)

    def test_missing_google_auth_library_reports_the_dependency(self) -> None:
        path = self.write_key_file()
        real_import = __import__

        def blocked_import(name, *args, **kwargs):
            if name.startswith("google."):
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked_import):
            with self.assertRaises(GoogleDriveAuthError) as caught:
                google_drive_auth._load_credentials(path, (DRIVE_READONLY_SCOPE,))

        self.assertIn("google-auth", str(caught.exception))

    def test_failures_reach_the_importer_as_import_errors(self) -> None:
        with drive_env(GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE="/nonexistent/key.json"):
            with self.assertRaises(google_drive_import.GoogleDriveImportError) as caught:
                google_drive_import._headers()

        self.assertIn("not found", str(caught.exception))


class LegacyCompatibilityTests(NoNetworkTestCase):
    def test_static_access_token_still_authenticates(self) -> None:
        with drive_env(GOOGLE_DRIVE_ACCESS_TOKEN=LEGACY_TOKEN):
            headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], f"Bearer {LEGACY_TOKEN}")

    def test_bearer_token_alias_still_authenticates(self) -> None:
        with drive_env(GOOGLE_DRIVE_BEARER_TOKEN=LEGACY_TOKEN):
            headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], f"Bearer {LEGACY_TOKEN}")

    def test_no_credentials_sends_no_authorization_header(self) -> None:
        with drive_env():
            headers = google_drive_import._headers()

        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Accept"], "application/json")

    def test_service_account_is_preferred_over_a_static_access_token(self) -> None:
        path = self.write_key_file()
        credentials = FakeCredentials(tokens=[ACCESS_TOKEN])

        with drive_env(
            GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=path,
            GOOGLE_DRIVE_ACCESS_TOKEN=LEGACY_TOKEN,
        ):
            with patch.object(
                google_drive_auth, "_load_credentials", return_value=credentials
            ):
                headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], f"Bearer {ACCESS_TOKEN}")
        self.assertNotIn(LEGACY_TOKEN, headers["Authorization"])

    def test_blank_service_account_path_falls_back_to_the_static_token(self) -> None:
        with drive_env(
            GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE="   ",
            GOOGLE_DRIVE_ACCESS_TOKEN=LEGACY_TOKEN,
        ):
            headers = google_drive_import._headers()

        self.assertEqual(headers["Authorization"], f"Bearer {LEGACY_TOKEN}")


class SharedDriveTests(NoNetworkTestCase):
    def list_with_env(self, drive_page, **env):
        path = self.write_key_file()
        credentials = FakeCredentials(tokens=[ACCESS_TOKEN])

        with drive_env(GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=path, **env):
            with patch.object(
                google_drive_auth, "_load_credentials", return_value=credentials
            ):
                with patch("urllib.request.urlopen") as urlopen:
                    urlopen.return_value = json_response(drive_page)
                    files = google_drive_import.list_folder_files(
                        f"https://drive.google.com/drive/folders/{SHARED_DRIVE_ID}",
                        max_files=10,
                    )
        request = urlopen.call_args.args[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        return files, request, query

    def test_listing_uses_the_service_account_token_and_shared_drive_flags(self) -> None:
        page = {
            "files": [
                {"id": "cv-1", "name": "cv.pdf", "mimeType": "application/pdf", "size": "2048"}
            ]
        }

        files, request, query = self.list_with_env(page)

        self.assertEqual([item.file_id for item in files], ["cv-1"])
        self.assertEqual(request.headers["Authorization"], f"Bearer {ACCESS_TOKEN}")
        self.assertEqual(query["supportsAllDrives"], ["true"])
        self.assertEqual(query["includeItemsFromAllDrives"], ["true"])
        self.assertIn(f"'{SHARED_DRIVE_ID}' in parents", query["q"][0])

    def test_shared_drive_id_scopes_the_corpus(self) -> None:
        page = {"files": [{"id": "cv-1", "mimeType": "application/pdf"}]}

        _, _, query = self.list_with_env(page, GOOGLE_DRIVE_SHARED_DRIVE_ID=SHARED_DRIVE_ID)

        self.assertEqual(query["corpora"], ["drive"])
        self.assertEqual(query["driveId"], [SHARED_DRIVE_ID])

    def test_corpus_scoping_is_off_by_default(self) -> None:
        page = {"files": [{"id": "cv-1", "mimeType": "application/pdf"}]}

        _, _, query = self.list_with_env(page)

        self.assertNotIn("corpora", query)
        self.assertNotIn("driveId", query)

    def test_interactive_import_limits_are_unchanged(self) -> None:
        """The 50/100 safety limits stay until the resumable importer lands."""
        page = {
            "nextPageToken": "unused",
            "files": [
                {"id": f"cv-{index}", "mimeType": "application/pdf"} for index in range(120)
            ],
        }
        path = self.write_key_file()
        credentials = FakeCredentials(tokens=[ACCESS_TOKEN])

        with drive_env(GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=path):
            with patch.object(
                google_drive_auth, "_load_credentials", return_value=credentials
            ):
                with patch("urllib.request.urlopen") as urlopen:
                    urlopen.return_value = json_response(page)
                    capped = google_drive_import.list_folder_files("root", max_files=1000)

        self.assertEqual(len(capped), 100)


class SecretRedactionTests(NoNetworkTestCase):
    def assert_no_secrets(self, text: str) -> None:
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def test_successful_refresh_logs_nothing_secret(self) -> None:
        provider, _ = self.provider(FakeCredentials(tokens=[ACCESS_TOKEN]))
        path = self.write_key_file()

        with self.assertLogs("cv_pipeline.google_drive_auth", level="DEBUG") as logs:
            provider.get_access_token(path)

        output = "\n".join(logs.output)
        self.assert_no_secrets(output)
        self.assertIn(SERVICE_ACCOUNT_EMAIL, output)

    def test_credential_load_logs_nothing_secret(self) -> None:
        path = self.write_key_file()

        class FakeServiceAccountCredentials:
            @staticmethod
            def from_service_account_info(info, scopes):  # noqa: ARG004
                return FakeCredentials()

        fake_module = types.ModuleType("google.oauth2.service_account")
        fake_module.Credentials = FakeServiceAccountCredentials

        with patch.dict(
            sys.modules,
            {
                "google": types.ModuleType("google"),
                "google.oauth2": types.ModuleType("google.oauth2"),
                "google.oauth2.service_account": fake_module,
            },
        ):
            with self.assertLogs("cv_pipeline.google_drive_auth", level="DEBUG") as logs:
                google_drive_auth._load_credentials(path, (DRIVE_READONLY_SCOPE,))

        self.assert_no_secrets("\n".join(logs.output))

    def test_corrupt_private_key_error_does_not_quote_key_material(self) -> None:
        path = self.write_key_file()

        class ExplodingCredentials:
            @staticmethod
            def from_service_account_info(info, scopes):  # noqa: ARG004
                raise ValueError(f"Unable to load PEM file: {PRIVATE_KEY}")

        fake_module = types.ModuleType("google.oauth2.service_account")
        fake_module.Credentials = ExplodingCredentials

        with patch.dict(
            sys.modules,
            {
                "google": types.ModuleType("google"),
                "google.oauth2": types.ModuleType("google.oauth2"),
                "google.oauth2.service_account": fake_module,
            },
        ):
            with self.assertRaises(GoogleDriveAuthError) as caught:
                google_drive_auth._load_credentials(path, (DRIVE_READONLY_SCOPE,))

        self.assert_no_secrets(str(caught.exception))
        self.assert_no_secrets(repr(caught.exception))
        self.assertIn("ValueError", str(caught.exception))

    def test_refresh_failure_error_does_not_quote_the_library_message(self) -> None:
        credentials = FakeCredentials()
        credentials.refresh_error = RuntimeError(f"body included {ACCESS_TOKEN}")
        provider, _ = self.provider(credentials)
        path = self.write_key_file()

        with self.assertLogs("cv_pipeline.google_drive_auth", level="DEBUG") as logs:
            with self.assertRaises(GoogleDriveAuthError) as caught:
                provider.get_access_token(path)

        self.assert_no_secrets(str(caught.exception))
        self.assert_no_secrets("\n".join(logs.output))

    def test_drive_http_errors_never_carry_the_authorization_header(self) -> None:
        path = self.write_key_file()
        credentials = FakeCredentials(tokens=[ACCESS_TOKEN])

        with drive_env(GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=path):
            with patch.object(
                google_drive_auth, "_load_credentials", return_value=credentials
            ):
                with patch("urllib.request.urlopen") as urlopen:
                    urlopen.side_effect = urllib.error.HTTPError(
                        "https://www.googleapis.com/drive/v3/files",
                        403,
                        "Forbidden",
                        {},
                        io.BytesIO(b'{"error": "forbidden"}'),
                    )
                    with self.assertRaises(
                        google_drive_import.GoogleDriveImportError
                    ) as caught:
                        google_drive_import.list_folder_files("root", max_files=1)

        self.assert_no_secrets(str(caught.exception))
        self.assertNotIn("Bearer", str(caught.exception))

    def test_provider_state_does_not_expose_key_material(self) -> None:
        provider, _ = self.provider(FakeCredentials(tokens=[ACCESS_TOKEN]))
        path = self.write_key_file()
        provider.get_access_token(path)

        self.assert_no_secrets(repr(provider))
        self.assert_no_secrets(repr(vars(provider).get("_credentials_key")))


class RepositoryHygieneTests(unittest.TestCase):
    """Guards against a real key being committed or baked into the image."""

    ROOT = Path(__file__).resolve().parents[1]

    def test_placeholder_is_not_a_usable_credential(self) -> None:
        placeholder = json.loads(
            (self.ROOT / "deploy" / "service-account.placeholder.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("private_key", placeholder)
        self.assertNotEqual(placeholder.get("type"), "service_account")

    def test_dockerignore_excludes_service_account_keys(self) -> None:
        patterns = (self.ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("*service-account*.json", patterns)
        self.assertIn("**/*service-account*.json", patterns)

    def test_gitignore_excludes_service_account_keys(self) -> None:
        patterns = (self.ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("*service-account*.json", patterns)
        self.assertIn("*service_account*.json", patterns)

    def test_requirements_pin_the_official_google_auth_package(self) -> None:
        for name in ("requirements.txt", "requirements-windows.txt"):
            text = (self.ROOT / "service" / name).read_text(encoding="utf-8")
            self.assertIn("google-auth==", text, name)
            self.assertIn("requests==", text, name)

    def test_env_examples_carry_empty_placeholders_only(self) -> None:
        examples = (
            self.ROOT / "config" / ".env_example",
            self.ROOT / "deploy" / "env.example",
            self.ROOT / "deploy" / "env.prod.example",
        )
        for path in examples:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GOOGLE_DRIVE_"):
                    self.assertTrue(
                        line.endswith("="),
                        f"{path.name} must not ship a value: {line}",
                    )

    def test_no_host_secret_path_is_hardcoded_in_application_source(self) -> None:
        source = (self.ROOT / "service" / "google_drive_auth.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/run/secrets/", source)
        self.assertNotIn("GOOGLE_DRIVE_SERVICE_ACCOUNT_HOST_FILE", source)


if __name__ == "__main__":
    unittest.main()
