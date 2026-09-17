from __future__ import annotations

import asyncio
import re
import unittest
from pathlib import Path

import yaml
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


ROOT = Path(__file__).resolve().parents[1]


class DeploymentSecurityTests(unittest.TestCase):
    def test_watcher_is_required_in_normal_production_stack(self) -> None:
        compose = yaml.safe_load((ROOT / "compose.prod.yml").read_text(encoding="utf-8"))
        watcher = compose["services"]["watcher"]

        self.assertNotIn("profiles", watcher)
        self.assertEqual(watcher["command"], ["python", "-m", "script.staging_watcher"])
        self.assertIn("healthcheck", watcher)

        deploy_script = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
        self.assertIn("for service in postgres api watcher frontend proxy", deploy_script)
        self.assertIn(".State.Restarting", deploy_script)

    def test_cookie_security_is_explicit_per_environment(self) -> None:
        prod = yaml.safe_load((ROOT / "compose.prod.yml").read_text(encoding="utf-8"))
        dev = yaml.safe_load((ROOT / "compose.dev.yml").read_text(encoding="utf-8"))
        env_example = (ROOT / "deploy" / "env.prod.example").read_text(encoding="utf-8")

        self.assertEqual(
            prod["services"]["api"]["environment"]["COOKIE_SECURE"],
            "${COOKIE_SECURE:?Set COOKIE_SECURE}",
        )
        self.assertEqual(
            dev["services"]["api"]["environment"]["COOKIE_SECURE"],
            "${COOKIE_SECURE:-false}",
        )
        self.assertIn("COOKIE_SECURE=true", env_example.splitlines())

    def test_proxy_preserves_outer_forwarding_headers(self) -> None:
        config = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

        self.assertIn("$http_x_forwarded_for $trusted_forwarded_for", config)
        self.assertIn("$http_x_forwarded_proto $trusted_forwarded_proto", config)
        self.assertIn("X-Forwarded-For $trusted_forwarded_for", config)
        self.assertIn("X-Forwarded-Proto $trusted_forwarded_proto", config)
        self.assertNotIn("X-Forwarded-Proto $scheme", config)
        self.assertNotIn("$proxy_add_x_forwarded_for", config)

    def test_uvicorn_proxy_middleware_resolves_original_client_and_https(self) -> None:
        captured = {}

        async def app(scope, receive, send):
            captured.update(scope)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/health",
            "raw_path": b"/api/v1/health",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"cv.example.com"),
                (b"x-forwarded-for", b"203.0.113.42"),
                (b"x-forwarded-proto", b"https"),
            ],
            "client": ("172.20.0.5", 45678),
            "server": ("api", 8000),
        }

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            return None

        middleware = ProxyHeadersMiddleware(app, trusted_hosts="*")
        asyncio.run(middleware(scope, receive, send))

        self.assertEqual(captured["client"][0], "203.0.113.42")
        self.assertEqual(captured["scheme"], "https")

    def test_production_api_trusts_headers_only_on_private_network(self) -> None:
        compose = yaml.safe_load((ROOT / "compose.prod.yml").read_text(encoding="utf-8"))
        api = compose["services"]["api"]
        proxy = compose["services"]["proxy"]

        self.assertNotIn("ports", api)
        self.assertIn("--proxy-headers", api["command"])
        self.assertIn("--forwarded-allow-ips=*", api["command"])
        self.assertEqual(proxy["ports"], ["${HTTP_BIND_ADDRESS:-127.0.0.1}:${HTTP_PORT:-8080}:80"])


class InnerProxyTimeoutTests(unittest.TestCase):
    """The inner nginx must outlive a Google Drive import.

    A Drive import is one long request: the API walks the Shared Drive and
    downloads each CV before responding. One measured at ~53s in production and
    was being cut off by nginx's 60s proxy_read_timeout default. These pin the
    hotfix into source so the next image cannot ship without it.
    """

    REQUIRED_API_TIMEOUTS = {
        "proxy_connect_timeout": "10s",
        "proxy_send_timeout": "300s",
        "proxy_read_timeout": "300s",
    }

    @staticmethod
    def _location_body(config: str, location: str) -> str:
        """Return the directives inside a single nginx location block."""
        start = config.index(f"location {location} {{")
        depth = 0
        for index in range(start, len(config)):
            if config[index] == "{":
                depth += 1
            elif config[index] == "}":
                depth -= 1
                if depth == 0:
                    return config[start : index + 1]
        raise AssertionError(f"unterminated location {location}")

    def setUp(self) -> None:
        self.config = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
        self.api_block = self._location_body(self.config, "/api/v1/")
        self.frontend_block = self._location_body(self.config, "/")

    def test_api_proxy_declares_the_required_timeouts(self) -> None:
        for directive, value in self.REQUIRED_API_TIMEOUTS.items():
            with self.subTest(directive=directive):
                self.assertIn(f"{directive} {value};", self.api_block)

    def test_api_read_timeout_outlives_a_slow_drive_import(self) -> None:
        # The production failure was a 53s import against a 60s default.
        match = re.search(r"proxy_read_timeout\s+(\d+)s;", self.api_block)
        self.assertIsNotNone(match, "the API proxy must set proxy_read_timeout")
        assert match is not None
        self.assertGreaterEqual(
            int(match.group(1)),
            120,
            "proxy_read_timeout must leave room for a long Drive import",
        )

    def test_api_connect_timeout_stays_short(self) -> None:
        # The API is one hop away on the internal network: a slow connect means
        # a dead upstream, not a slow one.
        match = re.search(r"proxy_connect_timeout\s+(\d+)s;", self.api_block)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertLessEqual(int(match.group(1)), 15)

    def test_timeouts_are_scoped_to_the_api_location_only(self) -> None:
        # The frontend proxy is deliberately left on nginx defaults.
        for directive in self.REQUIRED_API_TIMEOUTS:
            with self.subTest(directive=directive):
                self.assertNotIn(directive, self.frontend_block)

    def test_no_proxy_timeouts_leak_to_the_server_scope(self) -> None:
        # A server-level directive would silently apply to the frontend too.
        outside = self.config.replace(self.api_block, "")
        for directive in self.REQUIRED_API_TIMEOUTS:
            with self.subTest(directive=directive):
                self.assertNotIn(directive, outside)

    def test_api_proxy_keeps_its_forwarding_headers(self) -> None:
        # The timeout hotfix must not have disturbed the trust boundary.
        self.assertIn("proxy_pass http://api:8000/api/v1/;", self.api_block)
        self.assertIn("X-Forwarded-For $trusted_forwarded_for", self.api_block)
        self.assertIn("X-Forwarded-Proto $trusted_forwarded_proto", self.api_block)
        self.assertIn("X-Real-IP $trusted_real_ip", self.api_block)

    def test_config_is_balanced(self) -> None:
        self.assertEqual(self.config.count("{"), self.config.count("}"))


if __name__ == "__main__":
    unittest.main()
