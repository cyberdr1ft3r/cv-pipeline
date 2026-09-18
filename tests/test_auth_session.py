"""Session lifetime, cookie consistency and renewal.

The production bug these cover: the access token lived 30 minutes, nothing ever
extended it, and the frontend middleware sends an expired token to /login. An
active user was therefore logged out mid-session, and the next click - typically
a sidebar link - landed on the login page.

The fix is a sliding session: an authenticated caller can mint a fresh token via
POST /api/v1/auth/renew, and the cookie's Max-Age is derived from the same
constant as the JWT so the two cannot drift apart.
"""

from __future__ import annotations

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
from service import security
from service.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACCESS_TOKEN_EXPIRE_SECONDS,
    SESSION_RENEW_THRESHOLD_SECONDS,
    TokenPayload,
    create_access_token,
    verify_token,
)


SOURCER_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
RECRUITER_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"


def _user(
    user_id: str = SOURCER_ID,
    role: str = "sourcer",
    *,
    is_active: bool = True,
    deleted_at=None,
    email: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        role=role,
        email=email or f"{role}@itroad.ma",
        full_name=f"Test {role.title()}",
        hashed_password="unused",
        is_active=is_active,
        deleted_at=deleted_at,
    )


def cookie_attributes(response) -> dict[str, str]:
    """Parse the Set-Cookie header into a lowercase attribute map."""
    raw = response.headers["set-cookie"]
    attributes: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        attributes[key.strip().lower()] = value.strip().lower()
    return attributes


class SessionLifetimeConsistencyTests(unittest.TestCase):
    """The cookie and the JWT inside it must expire together."""

    def test_cookie_lifetime_is_derived_from_the_token_lifetime(self) -> None:
        self.assertEqual(ACCESS_TOKEN_EXPIRE_SECONDS, ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    def test_renew_threshold_is_shorter_than_the_token_lifetime(self) -> None:
        # Otherwise every request would renew, or none would.
        self.assertGreater(SESSION_RENEW_THRESHOLD_SECONDS, 0)
        self.assertLess(SESSION_RENEW_THRESHOLD_SECONDS, ACCESS_TOKEN_EXPIRE_SECONDS)

    def test_no_hardcoded_cookie_lifetime_remains_in_the_api(self) -> None:
        # The 1800 literal used to sit beside ACCESS_TOKEN_EXPIRE_MINUTES = 30,
        # free to drift the moment either changed.
        source = (Path(__file__).resolve().parents[1] / "service" / "api.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("max_age=1800", source)
        self.assertIn("max_age=ACCESS_TOKEN_EXPIRE_SECONDS", source)

    def test_issued_token_expiry_matches_the_cookie_lifetime(self) -> None:
        before = datetime.utcnow()
        token = create_access_token({"sub": SOURCER_ID, "role": "sourcer", "email": "s@itroad.ma"})
        payload = verify_token(token)

        self.assertIsNotNone(payload)
        assert payload is not None
        lifetime = payload.exp - before.replace(tzinfo=payload.exp.tzinfo)
        # Allow a second of slack for the clock between the two calls.
        self.assertAlmostEqual(
            lifetime.total_seconds(), ACCESS_TOKEN_EXPIRE_SECONDS, delta=2
        )


class LoginCookieTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(api.app)
        self.original_secure = api.COOKIE_SECURE
        self.addCleanup(setattr, api, "COOKIE_SECURE", self.original_secure)
        self.addCleanup(api.app.dependency_overrides.clear)

    def _login(self, user: SimpleNamespace, *, secure: bool = True):
        api.COOKIE_SECURE = secure
        with (
            patch.object(api, "get_user_by_email_any", return_value=user),
            patch("service.security.verify_password", return_value=True),
            patch.object(api, "update_last_login"),
            patch.object(api.audit_store, "log_event"),
        ):
            return self.client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "valid-password"},
            )

    def test_login_sets_a_secure_session_cookie_with_the_derived_lifetime(self) -> None:
        response = self._login(_user())

        self.assertEqual(response.status_code, 200)
        attributes = cookie_attributes(response)
        self.assertEqual(attributes["max-age"], str(ACCESS_TOKEN_EXPIRE_SECONDS))
        self.assertIn("httponly", attributes)
        self.assertIn("secure", attributes)
        self.assertEqual(attributes["samesite"], "lax")
        self.assertEqual(attributes["path"], "/")

    def test_login_cookie_contains_a_token_the_api_accepts(self) -> None:
        response = self._login(_user())

        token = response.cookies.get("access_token")
        self.assertIsNotNone(token)
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.sub, SOURCER_ID)
        self.assertEqual(payload.role, "sourcer")

    def test_development_login_cookie_is_usable_over_http(self) -> None:
        response = self._login(_user(), secure=False)

        attributes = cookie_attributes(response)
        self.assertNotIn("secure", attributes)
        self.assertIn("httponly", attributes)


class SessionRenewalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(api.app)
        self.original_secure = api.COOKIE_SECURE
        api.COOKIE_SECURE = True
        self.addCleanup(setattr, api, "COOKIE_SECURE", self.original_secure)
        self.addCleanup(api.app.dependency_overrides.clear)

    def _renew(self, user: SimpleNamespace | None, token: str | None = None):
        """Call the renew endpoint with the real get_current_user dependency."""
        if token is None and user is not None:
            token = create_access_token(
                {"sub": str(user.id), "role": user.role, "email": user.email}
            )
        with patch.object(api, "get_user_by_id", return_value=user):
            return self.client.post(
                "/api/v1/auth/renew",
                cookies={"access_token": token} if token else {},
            )

    def test_an_active_session_can_be_renewed(self) -> None:
        response = self._renew(_user())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["expires_in"], ACCESS_TOKEN_EXPIRE_SECONDS)

    def test_renewal_issues_a_cookie_with_the_same_security_attributes(self) -> None:
        response = self._renew(_user())

        attributes = cookie_attributes(response)
        self.assertEqual(attributes["max-age"], str(ACCESS_TOKEN_EXPIRE_SECONDS))
        self.assertIn("httponly", attributes)
        self.assertIn("secure", attributes)
        self.assertEqual(attributes["samesite"], "lax")
        self.assertEqual(attributes["path"], "/")

    def test_renewal_extends_the_expiry(self) -> None:
        user = _user()
        old_token = create_access_token(
            {"sub": str(user.id), "role": user.role, "email": user.email},
            expires_delta=timedelta(seconds=60),
        )

        response = self._renew(user, token=old_token)

        self.assertEqual(response.status_code, 200)
        old_payload = verify_token(old_token)
        new_payload = verify_token(response.cookies["access_token"])
        assert old_payload is not None and new_payload is not None
        self.assertGreater(new_payload.exp, old_payload.exp)

    def test_renewal_preserves_the_role(self) -> None:
        for role in ("sourcer", "recruiter", "admin"):
            with self.subTest(role=role):
                response = self._renew(_user(role=role))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["role"], role)
                payload = verify_token(response.cookies["access_token"])
                assert payload is not None
                self.assertEqual(payload.role, role)

    def test_renewal_takes_the_role_from_the_database_not_the_old_token(self) -> None:
        # A stale token must not let a demoted user keep elevated access, and a
        # promoted user should not have to log out and back in.
        stale_token = create_access_token(
            {"sub": SOURCER_ID, "role": "admin", "email": "sourcer@itroad.ma"}
        )

        response = self._renew(_user(role="sourcer"), token=stale_token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "sourcer")
        payload = verify_token(response.cookies["access_token"])
        assert payload is not None
        self.assertEqual(payload.role, "sourcer")

    def test_an_expired_token_cannot_be_renewed(self) -> None:
        expired = create_access_token(
            {"sub": SOURCER_ID, "role": "sourcer", "email": "s@itroad.ma"},
            expires_delta=timedelta(seconds=-1),
        )

        response = self._renew(_user(), token=expired)

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_renewal_without_a_session_is_rejected(self) -> None:
        response = self.client.post("/api/v1/auth/renew")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_a_garbage_token_cannot_be_renewed(self) -> None:
        response = self._renew(_user(), token="not-a-jwt")

        self.assertEqual(response.status_code, 401)

    def test_a_token_signed_with_another_key_cannot_be_renewed(self) -> None:
        import jwt

        forged = jwt.encode(
            {
                "sub": SOURCER_ID,
                "role": "admin",
                "email": "attacker@example.test",
                "exp": datetime.utcnow() + timedelta(minutes=30),
                "iat": datetime.utcnow(),
                "iss": "cv-pipeline-api",
            },
            "a-different-secret-key-that-is-long-enough",
            algorithm=security.ALGORITHM,
        )

        response = self._renew(_user(role="admin"), token=forged)

        self.assertEqual(response.status_code, 401)

    def test_a_deactivated_user_cannot_renew(self) -> None:
        response = self._renew(_user(is_active=False))

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_a_deleted_user_cannot_renew(self) -> None:
        response = self._renew(_user(deleted_at=datetime.utcnow()))

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_a_vanished_user_cannot_renew(self) -> None:
        response = self._renew(None)

        self.assertEqual(response.status_code, 401)


class SourcerCandidateAccessTests(unittest.TestCase):
    """Sourcers are allowed on the candidate APIs; RBAC is not weakened here."""

    def setUp(self) -> None:
        self.client = TestClient(api.app)
        self.addCleanup(api.app.dependency_overrides.clear)

    def _as(self, role: str, user_id: str = SOURCER_ID) -> None:
        api.app.dependency_overrides[api.get_current_user] = lambda: TokenPayload(
            sub=user_id,
            role=role,
            email=f"{role}@itroad.ma",
            exp=datetime.utcnow() + timedelta(minutes=30),
            iat=datetime.utcnow(),
        )

    def test_a_sourcer_can_list_candidates(self) -> None:
        self._as("sourcer")
        with (
            patch.object(api, "check_rate_limit"),
            patch.object(
                api,
                "store_list_candidates",
                return_value={"candidates": [{"id": "c1"}], "total": 1},
            ),
        ):
            response = self.client.get("/api/v1/candidates")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_every_space_role_can_list_candidates(self) -> None:
        for role in ("sourcer", "recruiter", "admin"):
            with self.subTest(role=role):
                self._as(role)
                with (
                    patch.object(api, "check_rate_limit"),
                    patch.object(
                        api, "store_list_candidates", return_value={"candidates": [], "total": 0}
                    ),
                ):
                    response = self.client.get("/api/v1/candidates")

                self.assertEqual(response.status_code, 200)

    def test_listing_candidates_without_a_session_is_401_not_403(self) -> None:
        # The frontend distinguishes the two: 401 ends the session, 403 does not.
        response = self.client.get("/api/v1/candidates")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
