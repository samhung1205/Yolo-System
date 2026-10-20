"""Use the real Docker CLI formatter against a temporary fake Unix API.

Never connects to the real Docker daemon or inspects real container settings.
"""
import copy
from http.server import BaseHTTPRequestHandler
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_compose_apply.py"
spec = importlib.util.spec_from_file_location("batch_inspect", SOURCE)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

PAYLOAD = {"Id": "a" * 64, "Image": "sha256:" + "b" * 64,
           "Config": {"User": "1007:1007", "Labels": None},
           "State": {"Running": True}, "Mounts": [],
           "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}, "NetworkMode": "host"}}


class TemplateTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("docker"):
            self.skipTest("Docker CLI unavailable")
        self.payload = copy.deepcopy(PAYLOAD)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_HEAD(self):
                self.send_response(200)
                self.send_header("API-Version", "1.47")
                self.end_headers()
            def do_GET(self):
                body = json.dumps(owner.payload).encode()
                self.send_response(200)
                self.send_header("API-Version", "1.47")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.directory = tempfile.TemporaryDirectory(prefix="yolo-format-", dir="/tmp")
        self.addCleanup(self.directory.cleanup)
        self.socket = str(Path(self.directory.name) / "api.sock")
        try:
            self.server = socketserver.UnixStreamServer(self.socket, Handler)
        except PermissionError:
            self.skipTest("Sandbox disallows local Unix socket; run this test with local socket access")
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def format(self, template):
        env = {k: v for k, v in os.environ.items() if k not in ("DOCKER_HOST", "DOCKER_CONTEXT")}
        env["DOCKER_API_VERSION"] = "1.47"
        return subprocess.run(["docker", "--host", "unix://" + self.socket,
                               "inspect", "--format", template, "sample"],
                              env=env, text=True, capture_output=True, timeout=10)

    def test_nil_labels_and_absent_health_are_normalized(self):
        fixed = self.format(app.INSPECT)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        actual = app.parse_inspect(fixed.stdout)
        self.assertIsNone(actual["project"])
        self.assertIsNone(actual["service"])
        self.assertIsNone(actual["health"])
        self.assertEqual(actual["user"], "1007:1007")

    def test_empty_labels_and_missing_healthcheck(self):
        self.payload["Config"]["Labels"] = {}
        fixed = self.format(app.INSPECT)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        self.assertIsNone(app.parse_inspect(fixed.stdout)["health"])

    def test_compose_labels_and_healthy_status(self):
        self.payload["Config"]["Labels"] = {"com.docker.compose.project": "sam-yolo",
                                             "com.docker.compose.service": "backend"}
        self.payload["State"]["Health"] = {"Status": "healthy"}
        fixed = self.format(app.INSPECT)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        actual = app.parse_inspect(fixed.stdout)
        self.assertEqual((actual["project"], actual["service"], actual["health"]),
                         ("sam-yolo", "backend", "healthy"))

    def test_missing_labels_key(self):
        del self.payload["Config"]["Labels"]
        fixed = self.format(app.INSPECT)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        self.assertIsNone(app.parse_inspect(fixed.stdout)["project"])


class ErrorClassificationTests(unittest.TestCase):
    def setUp(self):
        self.batch = app.Batch()
        self.addCleanup(self.batch.session.close)

    def test_optional_missing_container_returns_none(self):
        result = subprocess.CompletedProcess([], 1, "", "Error: No such object: sample")
        with patch.object(app.subprocess, "run", return_value=result):
            self.assertIsNone(self.batch.docker("inspect", "sample", optional=True))

    def test_optional_daemon_failure_is_not_treated_as_absent_container(self):
        result = subprocess.CompletedProcess([], 1, "", "Cannot connect to the Docker daemon")
        with patch.object(app.subprocess, "run", return_value=result):
            with self.assertRaises(app.Failed):
                self.batch.docker("inspect", "sample", optional=True)

    def test_template_error_does_not_print_raw_output(self):
        result = subprocess.CompletedProcess([], 1, "", "template parsing error: hidden-payload")
        with patch.object(app.subprocess, "run", return_value=result):
            with self.assertRaises(app.Failed) as error:
                self.batch.docker("inspect", "sample")
        self.assertIn("樣板", str(error.exception))
        self.assertNotIn("hidden-payload", str(error.exception))


if __name__ == "__main__":
    unittest.main()
