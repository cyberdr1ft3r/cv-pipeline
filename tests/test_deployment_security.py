from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


ROOT = Path(__file__).resolve().parents[1]


class DeploymentSecurityTests(unittest.TestCase):
    def test_watcher_is_profiled_but_configuration_is_preserved(self) -> None:
        compose = yaml.safe_load((ROOT / "compose.prod.yml").read_text(encoding="utf-8"))
        watcher = compose["services"]["watcher"]
        api = compose["services"]["api"]

        self.assertEqual(watcher["profiles"], ["watcher"])
        self.assertEqual(watcher["image"], api["image"])
        self.assertEqual(watcher["command"], ["python", "-m", "script.staging_watcher"])
        self.assertIn("environment", watcher)
        self.assertEqual(
            watcher["environment"]["OPENROUTER_API_KEY"],
            "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY}",
        )
        self.assertIn("cv_storage:/sftp/cv_tech/files", watcher["volumes"])
        self.assertIn("./config:/app/config:ro", watcher["volumes"])
        self.assertIn("healthcheck", watcher)
        self.assertIn("postgres", watcher["depends_on"])
        self.assertIn("api", watcher["depends_on"])

    def test_deploy_script_defaults_to_core_services_and_stops_watcher(self) -> None:
        deploy_script = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("DEPLOY_WATCHER=${DEPLOY_WATCHER:-0}", deploy_script)
        self.assertIn(
            'DEPLOY_SERVICES="postgres api frontend proxy"',
            deploy_script,
        )
        self.assertIn(
            "compose_base --profile watcher stop watcher",
            deploy_script,
        )
        self.assertIn("for service in $REQUIRED_SERVICES", deploy_script)
        self.assertIn(".State.Restarting", deploy_script)

    def test_explicit_watcher_mode_activates_profile_and_service(self) -> None:
        deploy_script = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn('if [ "$DEPLOY_WATCHER" = "1" ]; then', deploy_script)
        self.assertIn("compose_base --profile watcher", deploy_script)
        self.assertIn(
            'DEPLOY_SERVICES="postgres api watcher frontend proxy"',
            deploy_script,
        )
        self.assertIn(
            "compose up -d --remove-orphans $DEPLOY_SERVICES",
            deploy_script,
        )

    def test_rollback_preserves_recorded_watcher_mode(self) -> None:
        deploy_script = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
        rollback_script = (ROOT / "deploy" / "rollback.sh").read_text(encoding="utf-8")

        self.assertIn(
            'printf \'%s\\n\' "$DEPLOY_WATCHER" > "$WATCHER_MODE_FILE"',
            deploy_script,
        )
        self.assertIn('DEPLOY_WATCHER=$(tr -d \'\\r\\n\'', rollback_script)
        self.assertIn("export DEPLOY_WATCHER", rollback_script)

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


class DeploymentScriptModeTests(unittest.TestCase):
    def _run_deploy(
        self,
        watcher_mode: str,
        *,
        health_ok: bool = True,
        current_version: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        deploy_dir = root / "deploy"
        deploy_dir.mkdir()
        shutil.copy2(ROOT / "deploy" / "deploy.sh", deploy_dir / "deploy.sh")
        shutil.copy2(ROOT / "deploy" / "healthcheck.sh", deploy_dir / "healthcheck.sh")
        shutil.copy2(ROOT / "compose.prod.yml", root / "compose.prod.yml")
        (deploy_dir / ".env.prod").write_text("", encoding="utf-8")
        if current_version is not None:
            (deploy_dir / ".deployed-version").write_text(
                current_version + "\n",
                encoding="utf-8",
            )

        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        docker_log = root / "docker.log"
        docker = fake_bin / "docker"
        docker.write_text(
            """#!/usr/bin/env sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
if [ "$1" = "inspect" ]; then
  echo "running false healthy"
  exit 0
fi
last=""
for argument in "$@"; do
  last=$argument
done
case " $* " in
  *" ps -q "*) echo "cid-$last" ;;
  *" port proxy 80 "*) echo "127.0.0.1:8080" ;;
esac
exit 0
""",
            encoding="utf-8",
        )
        curl = fake_bin / "curl"
        curl.write_text(
            """#!/usr/bin/env sh
exit "${FAKE_HEALTH_EXIT:-0}"
""",
            encoding="utf-8",
        )
        sleep = fake_bin / "sleep"
        sleep.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        for executable in (docker, curl, sleep, deploy_dir / "deploy.sh", deploy_dir / "healthcheck.sh"):
            executable.chmod(0o755)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "DOCKER_LOG": str(docker_log),
                "DEPLOY_WATCHER": watcher_mode,
                "HEALTHCHECK_ATTEMPTS": "1",
                "FAKE_HEALTH_EXIT": "0" if health_ok else "1",
            }
        )
        result = subprocess.run(
            [str(deploy_dir / "deploy.sh"), "test-version"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        lines = (
            docker_log.read_text(encoding="utf-8").splitlines()
            if docker_log.exists()
            else []
        )
        return result, lines

    @staticmethod
    def _commands(lines: list[str], fragment: str) -> list[str]:
        return [line for line in lines if fragment in f" {line} "]

    def test_default_mode_stops_watcher_and_targets_only_core_services(self) -> None:
        result, lines = self._run_deploy("0")

        self.assertEqual(result.returncode, 0, result.stderr)
        stop_commands = self._commands(lines, " stop watcher ")
        self.assertEqual(len(stop_commands), 1)
        self.assertIn("--profile watcher", stop_commands[0])

        up_commands = self._commands(lines, " up -d --remove-orphans ")
        self.assertEqual(len(up_commands), 1)
        self.assertTrue(
            up_commands[0].endswith(
                "up -d --remove-orphans postgres api frontend proxy"
            )
        )
        self.assertNotIn("--profile watcher", up_commands[0])

        verified = {
            line.rsplit(" ", 1)[-1]
            for line in self._commands(lines, " ps -q ")
        }
        self.assertEqual(verified, {"postgres", "api", "frontend", "proxy"})

    def test_enabled_mode_activates_profile_deploys_and_verifies_watcher(self) -> None:
        result, lines = self._run_deploy("1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._commands(lines, " stop watcher "), [])

        up_commands = self._commands(lines, " up -d --remove-orphans ")
        self.assertEqual(len(up_commands), 1)
        self.assertIn("--profile watcher", up_commands[0])
        self.assertTrue(
            up_commands[0].endswith(
                "up -d --remove-orphans postgres api watcher frontend proxy"
            )
        )

        verified = {
            line.rsplit(" ", 1)[-1]
            for line in self._commands(lines, " ps -q ")
        }
        self.assertEqual(
            verified,
            {"postgres", "api", "watcher", "frontend", "proxy"},
        )

    def test_automatic_rollback_reuses_same_service_and_profile_mode(self) -> None:
        for watcher_mode in ("0", "1"):
            with self.subTest(watcher_mode=watcher_mode):
                result, lines = self._run_deploy(
                    watcher_mode,
                    health_ok=False,
                    current_version="previous-version",
                )

                self.assertEqual(result.returncode, 1)
                up_commands = self._commands(
                    lines,
                    " up -d --remove-orphans ",
                )
                self.assertEqual(len(up_commands), 2)
                self.assertEqual(
                    [
                        command.split(" up -d --remove-orphans ", 1)[1]
                        for command in up_commands
                    ],
                    [
                        "postgres api watcher frontend proxy"
                        if watcher_mode == "1"
                        else "postgres api frontend proxy"
                    ]
                    * 2,
                )
                self.assertEqual(
                    ["--profile watcher" in command for command in up_commands],
                    [watcher_mode == "1", watcher_mode == "1"],
                )


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
