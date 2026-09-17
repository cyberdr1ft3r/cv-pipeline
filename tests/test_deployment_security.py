from __future__ import annotations

import asyncio
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


if __name__ == "__main__":
    unittest.main()
