from __future__ import annotations

import tempfile
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

cv_alignment_stub = types.ModuleType("service.cv_alignment")
cv_alignment_stub.align_cv_to_offer = lambda *args, **kwargs: None
cv_alignment_stub.create_alignment_workspace = lambda *args, **kwargs: None
cv_alignment_stub.list_recent_alignments = lambda *args, **kwargs: []
cv_alignment_stub.read_alignment_status = lambda *args, **kwargs: {}
cv_alignment_stub.resolve_alignment_download = lambda *args, **kwargs: Path("unused")
cv_alignment_stub.write_alignment_status = lambda *args, **kwargs: None
sys.modules.setdefault("service.cv_alignment", cv_alignment_stub)

import service.api as api
from service.google_drive_import import DriveFile
from service.models import PipelineArtifacts, PipelineJob
from service.security import TokenPayload


JOB_ID = "11111111-1111-4111-8111-111111111111"
OTHER_JOB_ID = "22222222-2222-4222-8222-222222222222"
OWNER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ASSIGNED_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OFFER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def _token(user_id: str, role: str = "recruiter") -> TokenPayload:
    return TokenPayload(
        sub=user_id,
        role=role,
        email=f"{user_id[:8]}@example.test",
        exp=datetime.utcnow() + timedelta(minutes=5),
        iat=datetime.utcnow(),
    )


def _job(
    job_id: str = JOB_ID,
    *,
    created_by: str | None = OWNER_ID,
    offer_id: str | None = OFFER_ID,
    session_id: str = "20260101010101",
) -> PipelineJob:
    return PipelineJob(
        job_id=job_id,
        session_id=session_id,
        status="succeeded",
        stage="format_complete",
        created_at=datetime.utcnow(),
        offer_id=offer_id,
        created_by=created_by,
        artifacts=PipelineArtifacts(),
    )


def _offer(created_by: str = OWNER_ID, assigned_to: str | None = ASSIGNED_ID):
    return SimpleNamespace(
        id=OFFER_ID,
        created_by=created_by,
        assigned_to=assigned_to,
        session_id="20260101010101",
    )


class ApiSecurityBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(api.app)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.originals = {
            "API_JOBS_DIR": api.API_JOBS_DIR,
            "CURRENT_DIR": api.CURRENT_DIR,
            "_WATCHER_STAGING_PATH": api._WATCHER_STAGING_PATH,
            "get_job": api.get_job,
            "get_job_by_session_id": api.get_job_by_session_id,
            "get_offer_by_id": api.get_offer_by_id,
            "get_drive_file_metadata": api.get_drive_file_metadata,
            "download_drive_file": api.download_drive_file,
            "list_drive_folder_files": api.list_drive_folder_files,
        }
        api.API_JOBS_DIR = self.root / "api_jobs"
        api.CURRENT_DIR = self.root / "current"
        api._WATCHER_STAGING_PATH = str(self.root / "staging")
        api.app.dependency_overrides.clear()

    def tearDown(self) -> None:
        api.app.dependency_overrides.clear()
        for name, value in self.originals.items():
            setattr(api, name, value)
        self.tmp.cleanup()

    def _authenticate(self, user_id: str, role: str = "recruiter") -> None:
        api.app.dependency_overrides[api.get_current_user] = lambda: _token(user_id, role)

    def _mock_job_and_offer(
        self,
        *,
        job: PipelineJob | None = None,
        offer=None,
        session_job: PipelineJob | None = None,
    ) -> None:
        job = job if job is not None else _job()
        offer = offer if offer is not None else _offer()

        def fake_get_job(job_id: str):
            return job if job_id == job.job_id else None

        def fake_get_session(session_id: str):
            target = session_job if session_job is not None else job
            return target if target and target.session_id == session_id else None

        api.get_job = fake_get_job
        api.get_job_by_session_id = fake_get_session
        api.get_offer_by_id = lambda offer_id: offer if str(offer_id) == OFFER_ID else None

    def _write_logs(self, job_id: str = JOB_ID) -> None:
        logs = api.API_JOBS_DIR / job_id / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "pipeline_stdout.log").write_text("ok", encoding="utf-8")

    def test_anonymous_job_logs_progress_and_sessions_return_401(self) -> None:
        for method, path in [
            ("get", f"/api/v1/jobs/{JOB_ID}/logs"),
            ("get", f"/api/v1/jobs/{JOB_ID}/progress"),
            ("get", "/api/v1/sessions"),
        ]:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)

    def test_owner_or_assigned_user_can_access_job_logs(self) -> None:
        self._mock_job_and_offer()
        self._write_logs()

        self._authenticate(OWNER_ID, "recruiter")
        self.assertEqual(self.client.get(f"/api/v1/jobs/{JOB_ID}/logs").status_code, 200)

        self._authenticate(ASSIGNED_ID, "sourcer")
        self.assertEqual(self.client.get(f"/api/v1/jobs/{JOB_ID}/logs").status_code, 200)

    def test_unrelated_authenticated_user_is_denied(self) -> None:
        self._mock_job_and_offer()
        self._write_logs()
        self._authenticate(OTHER_ID, "recruiter")

        response = self.client.get(f"/api/v1/jobs/{JOB_ID}/logs")

        self.assertEqual(response.status_code, 404)

    def test_admin_can_access_job_logs(self) -> None:
        self._mock_job_and_offer(job=_job(created_by=None, offer_id=None))
        self._write_logs()
        self._authenticate(OTHER_ID, "admin")

        response = self.client.get(f"/api/v1/jobs/{JOB_ID}/logs")

        self.assertEqual(response.status_code, 200)

    def test_artifact_download_uses_same_access_policy(self) -> None:
        self._mock_job_and_offer()
        result_dir = api.CURRENT_DIR / "final_result" / "20260101010101"
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "final_result.json").write_text("{}", encoding="utf-8")
        self._authenticate(OTHER_ID, "recruiter")

        result_denied = self.client.get(f"/api/v1/jobs/{JOB_ID}/results")
        self.assertEqual(result_denied.status_code, 404)

        denied = self.client.get(f"/api/v1/jobs/{JOB_ID}/download/final_result")
        self.assertEqual(denied.status_code, 404)

        self._authenticate(OWNER_ID, "recruiter")
        result_allowed = self.client.get(f"/api/v1/jobs/{JOB_ID}/results")
        self.assertEqual(result_allowed.status_code, 200)

        allowed = self.client.get(f"/api/v1/jobs/{JOB_ID}/download/final_result")
        self.assertEqual(allowed.status_code, 200)

    def test_session_reuse_cannot_access_unrelated_user_session(self) -> None:
        self._mock_job_and_offer(session_job=_job(created_by=OWNER_ID, offer_id=None))
        self._authenticate(OTHER_ID, "recruiter")

        response = self.client.post(
            "/api/v1/jobs",
            data={"reuse_session_id": "20260101010101"},
        )

        self.assertEqual(response.status_code, 404)

    def test_manual_upload_cannot_escape_staging(self) -> None:
        self._authenticate(OWNER_ID, "sourcer")

        response = self.client.post(
            "/api/v1/staging/upload",
            data={"profile": "../../escape"},
            files={"file": ("cv.pdf", b"pdf", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "escape").exists())

    def test_drive_import_cannot_escape_staging(self) -> None:
        self._authenticate(OWNER_ID, "sourcer")
        api.get_drive_file_metadata = lambda url: DriveFile("file1", "cv.pdf", "application/pdf", size=3)
        api.download_drive_file = lambda file_id, *, max_bytes: b"pdf"
        api.list_drive_folder_files = lambda folder_url, *, max_files: []

        response = self.client.post(
            "/api/v1/staging/google-drive/import",
            json={"file_urls": ["file1"], "profile": "../escape"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["failed_count"], 1)
        self.assertFalse((self.root / "escape").exists())


class AuthCookieSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(api.app)
        self.original_cookie_secure = api.COOKIE_SECURE

    def tearDown(self) -> None:
        api.COOKIE_SECURE = self.original_cookie_secure

    def _login(self, *, secure: bool):
        api.COOKIE_SECURE = secure
        user = SimpleNamespace(
            id=OWNER_ID,
            role="recruiter",
            email="owner@example.test",
            full_name="Test Owner",
            hashed_password="unused",
            deleted_at=None,
            is_active=True,
        )
        with (
            patch.object(api, "get_user_by_email_any", return_value=user),
            patch("service.security.verify_password", return_value=True),
            patch.object(api, "create_access_token", return_value="test-token"),
            patch.object(api, "update_last_login"),
            patch.object(api.audit_store, "log_event"),
        ):
            return self.client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "valid-password"},
            )

    def test_production_login_cookie_is_secure(self) -> None:
        response = self._login(secure=True)

        self.assertEqual(response.status_code, 200)
        attributes = {
            part.strip().lower()
            for part in response.headers["set-cookie"].split(";")
        }
        self.assertIn("secure", attributes)
        self.assertIn("httponly", attributes)
        self.assertIn("samesite=lax", attributes)
        self.assertIn("path=/", attributes)
        self.assertIn("max-age=1800", attributes)

    def test_development_login_cookie_remains_usable_over_http(self) -> None:
        response = self._login(secure=False)

        self.assertEqual(response.status_code, 200)
        attributes = {
            part.strip().lower()
            for part in response.headers["set-cookie"].split(";")
        }
        self.assertNotIn("secure", attributes)
        self.assertIn("httponly", attributes)
        self.assertIn("samesite=lax", attributes)

    def test_cookie_secure_environment_parser_is_strict(self) -> None:
        with patch.dict("os.environ", {"COOKIE_SECURE": "YeS"}):
            self.assertTrue(api._read_bool_env("COOKIE_SECURE", default=False))
        with patch.dict("os.environ", {"COOKIE_SECURE": "off"}):
            self.assertFalse(api._read_bool_env("COOKIE_SECURE", default=True))
        with patch.dict("os.environ", {"COOKIE_SECURE": "sometimes"}):
            with self.assertRaises(RuntimeError):
                api._read_bool_env("COOKIE_SECURE", default=False)


if __name__ == "__main__":
    unittest.main()
