"""Diagnostic boundaries: no secrets, no state changes, normal TLS validation."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "lab_https_diagnose.py"
spec = importlib.util.spec_from_file_location("lab_https_diagnose", SOURCE)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DiagnoseTests(unittest.TestCase):
    def test_logs_keep_startup_failure_without_access_credentials(self):
        logs = "\n".join([
            'Error: loading initial config: mkdir /data/caddy: permission denied',
            json.dumps({"level":"error", "logger":"http.log.access", "msg":"access_token=supersecret",
                        "request":{"headers":{"Authorization":["Bearer token"]}}}),
            json.dumps({"level":"error", "logger":"tls.obtain", "msg":"could not get certificate",
                        "error":"challenge failed: https://acme.example/abcdef?token=private password=hunter2"}),
        ])
        result = app.summarize_logs(logs)
        text = json.dumps(result)
        self.assertIn("permission denied", text)
        self.assertIn("challenge failed", text)
        for secret in ("supersecret", "Bearer token", "abcdef", "private", "hunter2"):
            self.assertNotIn(secret, text)

    def test_events_and_acme_types_are_retained(self):
        raw = json.dumps({"level":"info", "logger":"tls.obtain", "msg":"certificate obtained successfully"})
        raw += '\nError: urn:ietf:params:acme:error:connection'
        result = app.summarize_logs(raw)
        self.assertIn("certificate_obtained", result["events"])
        self.assertEqual(result["acme_types"], ["connection"])

    def test_plain_loader_console_and_non_tls_startup_failures_are_kept(self):
        raw = '\x1b[31mexec /usr/bin/caddy: operation not permitted\x1b[0m\n'
        raw += 'caddy: error while loading shared libraries: missing.so\n'
        raw += json.dumps({"level":"error", "logger":"http", "msg":"binding listener failed"})
        result = app.summarize_logs(raw)
        self.assertEqual(result["unparsed_lines"], 2)
        self.assertEqual(len(result["errors"]), 3)
        self.assertIn("operation not permitted", result["errors"][0])

    def test_plaintext_http_access_and_structured_request_errors_are_omitted(self):
        raw = '127.0.0.1 "GET /secret HTTP/1.1" 500 error sensitive\n'
        raw += json.dumps({"level":"error", "logger":"http", "msg":"sensitive", "request":{}})
        self.assertEqual(app.summarize_logs(raw)["errors"], [])

    def test_state_excludes_health_output_and_all_environment(self):
        raw = {"id":"gateway-id", "image":"sha256:image", "state":{
            "Status":"restarting", "ExitCode":1, "Health":{"Status":"unhealthy", "Log":[{"Output":"secret"}]}},
            "restarts":4, "labels":{"com.docker.compose.project":"sam-yolo", "com.docker.compose.service":"gateway"},
            "mounts":[{"Name":"sam-yolo-caddy-data", "Destination":"/data", "RW":True}],
            "network":"host", "read_only":True}
        with patch.object(app, "command", return_value=(json.dumps(raw), "")) as call:
            result, identifier = app.inspect_gateway()
        self.assertEqual(identifier, "gateway-id")
        self.assertEqual(result["restart_count"], 4)
        self.assertTrue(result["certificate_volume"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("Env", str(call.call_args))

    def test_foreign_gateway_logs_are_skipped(self):
        with patch.object(app, "http_json", return_value={}), \
             patch.object(app, "inspect_gateway", return_value=({"owned":False}, None)), \
             patch.object(app, "command", return_value=("", "")) as command, \
             patch.object(app, "verified_tls", return_value={}), patch.object(app, "requests_tls", return_value={}):
            result = app.collect("140.113.135.113")
        self.assertEqual(len(command.call_args_list), 1)
        self.assertEqual(command.call_args.args[0][0], "ss")
        self.assertIn("skipped", result["caddy_logs"])

    def test_socket_uses_default_ca_and_public_ip_san(self):
        with patch.object(app.socket, "create_connection") as connect, \
             patch.object(app.ssl, "create_default_context") as context:
            context.return_value.wrap_socket.return_value.__enter__.return_value.getpeercert.return_value = {"notAfter":"later"}
            result = app.verified_tls("140.113.135.113")
        context.assert_called_once_with()
        self.assertEqual(context.return_value.wrap_socket.call_args.kwargs, {"server_hostname":"140.113.135.113"})
        self.assertTrue(result["verified"])

    def test_requests_never_bypasses_certificate_validation(self):
        import requests
        with patch.object(requests, "Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.get.return_value.status_code = 200
            session.get.return_value.json.return_value = {"database":"connected"}
            result = app.requests_tls("140.113.135.113")
        self.assertTrue(result["verified"])
        self.assertFalse(session.trust_env)
        self.assertNotIn("verify", session.get.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
