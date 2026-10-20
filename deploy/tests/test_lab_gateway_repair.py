"""Gateway-only Snap NNP exception, runtime A/B evidence and safe recovery."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_gateway_repair.py"
with patch.object(sys, "path", [str(SOURCE.parent)] + sys.path):
    spec = importlib.util.spec_from_file_location("lab_gateway_repair", SOURCE)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


def config(image="new"):
    return {"name":"sam-yolo", "services":{"gateway":{
        "container_name":"sam-yolo-gateway", "image":image, "network_mode":"host", "read_only":True,
        "cap_drop":["ALL"], "cap_add":["NET_BIND_SERVICE"], "security_opt":["no-new-privileges:false"],
        "volumes":[{"type":"volume", "source":"caddy_data", "target":"/data"}]}},
        "volumes":{"caddy_data":{"name":"sam-yolo-caddy-data", "external":True}}}


class PolicyTests(unittest.TestCase):
    def test_only_nnp_flag_is_changed_and_images_are_preserved(self):
        original = "YOLO_PUBLIC_BACKEND_IMAGE=backend\nYOLO_UID=1007\nYOLO_PUBLIC_GATEWAY_IMAGE=old\n"
        result = app.nnp_env(original)
        self.assertEqual(result, original + "YOLO_GATEWAY_NNP=false\n")
        self.assertEqual(app.nnp_env(result), result)
        self.assertEqual(app.nnp_env(original + "YOLO_GATEWAY_NNP=true\n"), result)
        with self.assertRaises(app.Failed): app.nnp_env(result + "YOLO_GATEWAY_NNP=false\n")
        with self.assertRaises(app.Failed): app.nnp_env(original + "YOLO_GATEWAY_NNP=unknown\n")

    def test_compose_patch_preserves_custom_content_and_defaults_to_nnp_true(self):
        original = "# custom\n    " + app.NNP_ORIGINAL + "\n# keep\n"
        result = app.source_patch(original)
        self.assertEqual(result.replace(app.NNP_TEMPLATE, app.NNP_ORIGINAL), original)
        self.assertIn("${YOLO_GATEWAY_NNP:-true}", result)
        self.assertEqual(app.source_patch(result), result)
        with self.assertRaises(app.Failed): app.source_patch("unrelated yaml\n")

    def test_exact_gateway_policy_is_required(self):
        app.check_spec(config(), "new")
        for key, value in (("cap_add",["ALL"]), ("cap_drop",[]), ("security_opt",[]), ("read_only",False),
                           ("privileged",True), ("entrypoint",["sh"]), ("image","foreign"), ("network_mode","bridge")):
            document = config()
            document["services"]["gateway"][key] = value
            with self.subTest(key=key), self.assertRaises(app.Failed): app.check_spec(document, "new")
        document = config()
        document["services"]["gateway"]["volumes"].append({"type":"bind", "source":"/", "target":"/host"})
        with self.assertRaises(app.Failed): app.check_spec(document, "new")

    def test_execution_probe_uses_runtime_restrictions_without_mounting_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            with patch.object(batch, "docker", return_value="v2.11.7") as docker:
                batch.probe("image", "exec /usr/bin/caddy version", "false")
            args = docker.call_args.args
            self.assertIn("no-new-privileges:false", args)
            self.assertEqual(args[args.index("--network")+1], "none")
            self.assertIn("--read-only", args)
            self.assertEqual(args[args.index("--cap-drop")+1], "ALL")
            self.assertEqual(args[args.index("--cap-add")+1], "NET_BIND_SERVICE")
            self.assertNotIn("--mount", args)
            self.assertNotIn("-e", args)

    def test_only_reproduced_nnp_failure_allows_exception(self):
        valid = "NoNewPrivs: 0\nSeccomp: 2\nCapEff: 0000000000000400\nCapBnd: 0000000000000400\nAppArmor: docker-default (enforce)\nv2.11.7 h1:version\n"
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.old_image = "old"
            with patch.object(batch,"probe",side_effect=[app.Failed("exec /bin/sh: operation not permitted"),valid]) as probe, redirect_stdout(io.StringIO()):
                batch.validate_runtime()
            self.assertTrue(batch.compatibility_confirmed)
            self.assertEqual(probe.call_args_list[0].args[2], "true")
            self.assertEqual(probe.call_args_list[1].args[2], "false")

    def test_no_exception_when_nnp_failure_is_not_reproduced_or_controls_are_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.old_image = "old"
            with patch.object(batch,"probe",return_value="successful control"):
                with self.assertRaises(app.Failed): batch.validate_runtime()
            self.assertFalse(batch.compatibility_confirmed)
            with patch.object(batch,"probe",side_effect=[app.Failed("operation not permitted"),"NoNewPrivs: 0\nv2.11.7"]):
                with self.assertRaises(app.Failed): batch.validate_runtime()
            self.assertFalse(batch.compatibility_confirmed)

    def test_foreign_gateway_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            with patch.object(batch, "inspect", return_value={"project":"foreign","service":"gateway","image":"old"}):
                with self.assertRaises(app.Failed): batch.owned_gateway({"old"})

    def test_switch_mutates_only_gateway_and_preserves_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch = app.Repair(root, "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.work = root / "work"
            batch.work.mkdir()
            batch.old_image = batch.new_image = "old"
            batch.compatibility_confirmed = True
            batch.old_apparmor = "docker-default"
            batch.source = root / "compose.public.yaml"
            batch.source_before = app.NNP_ORIGINAL + "\n"
            batch.source_after = app.source_patch(batch.source_before)
            batch.source.write_text(batch.source_before)
            batch.env_path = root / "compose.env"
            batch.env_before = "YOLO_UID=1007\nYOLO_PUBLIC_BACKEND_IMAGE=backend\nYOLO_PUBLIC_GATEWAY_IMAGE=old\n"
            batch.env_path.write_text(batch.env_before)
            calls = []
            def docker(*args, **kwargs):
                calls.append(args)
                if args[-3:] == ("config","--format","json"): return json.dumps(config("old"))
                if args[0] == "inspect":
                    return json.dumps("docker-default") if "{{json .AppArmorProfile}}" in args else json.dumps({"Running":True,"Restarting":False})
                return "v2.11.7"
            with patch.object(batch, "docker", side_effect=docker), patch.object(batch, "unchanged"), \
                 patch.object(batch, "owned_gateway", return_value={"id":"gateway"}), \
                 patch.object(app.subprocess, "check_output", return_value="LISTEN 140.113.135.113:443"), redirect_stdout(io.StringIO()):
                batch.switch()
            changes = [args for args in calls if "up" in args]
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][-1], "gateway")
            self.assertIn("--no-deps", changes[0])
            self.assertEqual(batch.env_path.read_text(), app.nnp_env(batch.env_before))
            self.assertEqual(batch.env_path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(batch.startup_ok)

    def test_switch_without_runtime_evidence_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            with patch.object(batch,"docker") as docker:
                with self.assertRaises(app.Failed): batch.switch()
            docker.assert_not_called()

    def test_api_requests_use_verified_https_after_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Repair(Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.public = True
            with patch.object(batch.session, "request") as request:
                request.return_value.status_code = 200
                batch.request("/api/health")
            self.assertEqual(request.call_args.args[1], "https://140.113.135.113/api/health")
            self.assertNotIn("verify", request.call_args.kwargs)


class Simulation(app.Repair):
    def __init__(self, root, failure=None):
        super().__init__(root, "140.113.135.113")
        self.work = root / "report"
        self.failure = failure
        self.calls = []
    def prepare(self):
        self.work.mkdir()
        self.calls.append("preflight")
        if self.failure == "preflight": raise app.Failed("foreign gateway")
    def validate_runtime(self):
        self.calls.append("A/B check")
        if self.failure == "runtime": raise app.Failed("controls do not pass")
    def switch(self):
        self.env_changed = True
        self.calls.append("switch gateway")
        if self.failure == "startup": raise app.Failed("startup failure")
        self.startup_ok = True
    def trusted_https(self):
        if self.failure == "pending":
            self.report["https_pending"] = True
            return False
        return True
    def acceptance(self):
        self.calls.append("acceptance")
        if self.failure == "login": raise app.Failed("wrong password")
        self.report["success"] = True
    def unchanged(self): self.calls.append("check backend web mysql")
    def logs(self): self.calls.append("private gateway logs")
    def rollback(self): self.calls.append("restore gateway")


class WorkflowTests(unittest.TestCase):
    def run_case(self, failure=None):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulation(Path(folder), failure)
            with redirect_stdout(io.StringIO()): result = batch.run()
            report = json.loads((batch.work / "report.json").read_text())
            self.assertEqual(report["success"], result == 0)
            return batch, result

    def test_preflight_and_runtime_failure_never_replace_any_container(self):
        for failure in ("preflight", "runtime"):
            batch, result = self.run_case(failure)
            self.assertEqual(result, 1)
            self.assertNotIn("switch gateway", batch.calls)
            self.assertNotIn("restore gateway", batch.calls)

    def test_startup_failure_restores_only_gateway(self):
        batch, result = self.run_case("startup")
        self.assertEqual(result, 1)
        self.assertIn("restore gateway", batch.calls)

    def test_pending_certificate_keeps_executable_gateway(self):
        batch, result = self.run_case("pending")
        self.assertEqual(result, 2)
        self.assertNotIn("restore gateway", batch.calls)
        self.assertNotIn("acceptance", batch.calls)

    def test_incorrect_login_does_not_revert_successful_capability_fix(self):
        batch, result = self.run_case("login")
        self.assertEqual(result, 1)
        self.assertTrue(batch.startup_ok)
        self.assertNotIn("restore gateway", batch.calls)

    def test_success_verifies_services_and_acceptance(self):
        batch, result = self.run_case()
        self.assertEqual(result, 0)
        self.assertIn("acceptance", batch.calls)
        self.assertIn("check backend web mysql", batch.calls)


if __name__ == "__main__":
    unittest.main()
