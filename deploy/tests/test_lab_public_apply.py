"""Source-bundle checks, gateway policy, safe rollback and batch control flow."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_public_apply.py"
with patch.object(sys, "path", [str(SOURCE.parent)] + sys.path):
    spec = importlib.util.spec_from_file_location("lab_public_apply", SOURCE)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


class BundleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.repo = self.root / "repo"
        self.package = self.root / "package"
        self.repo.mkdir()
        self.package.mkdir()
        self.manifest = {"files":{}}
        for name in app.ALLOWED:
            target = self.repo / name
            source = self.package / "payload" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            source.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"before\n")
            source.write_bytes(b"after\n")
            self.manifest["files"][name] = {"before":app.file_hash(target), "after":app.file_hash(source),
                "before_lf":app.file_hash(target), "after_lf":app.file_hash(source)}
        self.save()

    def save(self):
        (self.package / "manifest.json").write_text(json.dumps(self.manifest))

    def test_all_preimages_checked_before_changes(self):
        _, plan = app.bundle_plan(self.repo, self.package)
        self.assertEqual(len(plan), len(app.ALLOWED))
        self.assertTrue(all(p.read_bytes() == b"before\n" for p in self.repo.rglob("*") if p.is_file()))

    def test_existing_updated_sources_are_idempotent(self):
        for name in app.ALLOWED:
            (self.repo / name).write_bytes(b"after\n")
        self.assertEqual(app.bundle_plan(self.repo, self.package)[1], [])

    def test_line_ending_only_difference_is_allowed(self):
        name = next(iter(app.ALLOWED))
        (self.repo / name).write_bytes(b"before\r\n")
        self.assertEqual(len(app.bundle_plan(self.repo, self.package)[1]), len(app.ALLOWED))

    def test_local_customization_is_not_overwritten(self):
        name = next(iter(app.ALLOWED))
        (self.repo / name).write_bytes(b"unrelated edits")
        with self.assertRaises(app.Failed):
            app.bundle_plan(self.repo, self.package)
        self.assertEqual((self.repo / name).read_bytes(), b"unrelated edits")

    def test_bundle_payload_tampering_is_rejected(self):
        (self.package / "payload" / next(iter(app.ALLOWED))).write_bytes(b"tampered")
        with self.assertRaises(app.Failed):
            app.bundle_plan(self.repo, self.package)

    def test_unlisted_path_and_target_symlinks_are_rejected(self):
        self.manifest["files"]["../outside"] = {"before":None, "after":"invalid"}
        self.save()
        with self.assertRaises(app.Failed):
            app.bundle_plan(self.repo, self.package)
        del self.manifest["files"]["../outside"]
        self.save()
        name = next(iter(app.ALLOWED))
        target = self.repo / name
        target.unlink()
        target.symlink_to(self.package / "payload" / name)
        with self.assertRaises(app.Failed):
            app.bundle_plan(self.repo, self.package)


class ConfigTests(unittest.TestCase):
    def config(self):
        return {"admin":{"disabled":True}, "apps":{
            "http":{"servers":{"server":{"listen":["140.113.135.113:443"]}}},
            "tls":{"automation":{"policies":[{"issuers":[{"module":"acme", "profile":"shortlived",
                "ca":"https://acme-v02.api.letsencrypt.org/directory", "challenges":{"http":{"disabled":True}}}]}]}}}}

    def test_only_public_ca_shortlived_on_specific_ip_is_accepted(self):
        app.check_gateway_config(self.config(), "140.113.135.113")

    def test_local_ca_other_ports_and_enabled_admin_are_rejected(self):
        base = self.config()
        variants = []
        for changes in ("issuer", "port", "admin", "profile", "http", "no_servers"):
            value = deepcopy(base)
            if changes == "issuer": value["apps"]["tls"]["automation"]["policies"][0]["issuers"][0]["module"] = "internal"
            if changes == "port": value["apps"]["http"]["servers"]["server"]["listen"] = [":443"]
            if changes == "admin": value["admin"]["disabled"] = False
            if changes == "profile": value["apps"]["tls"]["automation"]["policies"][0]["issuers"][0]["profile"] = "classic"
            if changes == "http": value["apps"]["tls"]["automation"]["policies"][0]["issuers"][0]["challenges"]["http"]["disabled"] = False
            if changes == "no_servers": value["apps"]["http"]["servers"] = {}
            variants.append(value)
        for value in variants:
            with self.subTest(config=value), self.assertRaises(app.Failed):
                app.check_gateway_config(value, "140.113.135.113")

    def test_authenticated_requests_and_sse_go_to_verified_https(self):
        session = app.GatewaySession()
        self.addCleanup(session.close)
        session.public_url = "https://140.113.135.113"
        with patch.object(app.requests.Session, "request") as request:
            session.post("http://127.0.0.1:8080/api/chat/stream", stream=True)
            self.assertEqual(request.call_args.args[1], "https://140.113.135.113/api/chat/stream")
            self.assertNotIn("verify", request.call_args.kwargs)
            session.get("http://127.0.0.1:8000/api/health")
            self.assertEqual(request.call_args.args[1], "http://127.0.0.1:8000/api/health")


class Simulation(app.Public):
    def __init__(self, root, failure=None):
        super().__init__(root, root, "140.113.135.113")
        self.work = root / "report"
        self.failure = failure
        self.calls = []

    def preflight(self):
        self.work.mkdir()
        if self.failure == "preflight": raise app.Failed("failed login")

    def sources_and_images(self): self.calls.append("build")
    def preflight_image(self): self.calls.append("image test")
    def update_backend(self):
        self.changed = True
        self.config_changed = True
        self.calls.append("backend")
        if self.failure == "backend": raise app.Failed("health failure")
        self.backend_ready = True
    def start_gateway(self):
        self.calls.append("gateway")
        if self.failure == "pending":
            self.report["https_pending"] = True
            return False
        self.session.public_url = "https://" + self.address
        return True
    def closed_signup(self): self.calls.append("closed signup")
    def verify_existing(self):
        self.calls.append("data")
        if self.failure == "data": raise app.Failed("data changed")
    def routes_and_gpu(self): self.calls.append("routes/GPU")
    def stream_check(self, agent=False):
        self.calls.append("agent" if agent else "chat")
        if self.failure == "sse": raise app.Failed("SSE failed")
    def rollback_backend(self): self.calls.append("rollback")
    def cleanup_temp(self): self.calls.append("cleanup temporary")


class WorkflowTests(unittest.TestCase):
    def test_closed_policy_must_be_confirmed_before_posting_registration_probe(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Public(Path(folder), Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            with patch.object(batch, "request") as request:
                request.return_value.json.return_value = {"registration_enabled":True}
                with self.assertRaises(app.Failed): batch.closed_signup()
                self.assertEqual(request.call_count, 1)

    def test_compose_image_is_persisted_and_rollback_uses_original_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch = app.Public(root, root, "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.work = root / "release"
            batch.work.mkdir()
            batch.compose_env = root / "compose.env"
            batch.compose_env.write_text("YOLO_UID=1007\nYOLO_GID=1007\nYOLO_REPO_ROOT=/home/sam/apps/Yolo_system\n")
            batch.compose_env.chmod(0o600)
            batch.original = {"backend":{"image":app.IMAGES["backend"], "id":"original"}}
            batch.images = {"backend":"sha256:" + "a"*64, "gateway":"sha256:" + "b"*64}
            def inspect(name, optional=False):
                return None if name == "sam-yolo-gateway" else {"project":"sam-yolo", "service":"backend", "image":batch.images["backend"]}
            with patch.object(batch, "docker", return_value="{}"), patch.object(batch, "idle"), \
                 patch.object(batch, "wait_backend"), patch.object(batch, "closed_signup"), patch.object(batch, "verify_existing"), \
                 patch.object(batch, "inspect", side_effect=inspect), redirect_stdout(io.StringIO()):
                batch.update_backend()
                self.assertIn("YOLO_UID=1007\n", batch.compose_env.read_text())
                self.assertIn("YOLO_PUBLIC_BACKEND_IMAGE=" + batch.images["backend"], batch.compose_env.read_text())
                self.assertEqual(batch.compose_env.stat().st_mode & 0o777, 0o600)
                batch.rollback_backend()
                self.assertIn("YOLO_PUBLIC_BACKEND_IMAGE=" + app.IMAGES["backend"], batch.compose_env.read_text())
                self.assertTrue(batch.report["rollback_verified"])

    def run_batch(self, failure=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        batch = Simulation(Path(directory.name), failure)
        with redirect_stdout(io.StringIO()):
            code = batch.run()
        report = json.loads((batch.work / "report.json").read_text())
        self.assertEqual(report["success"], code == 0)
        return batch, code

    def test_full_public_flow_checks_data_gpu_and_both_streams(self):
        batch, code = self.run_batch()
        self.assertEqual(code, 0)
        self.assertIn("chat", batch.calls)
        self.assertIn("agent", batch.calls)
        self.assertNotIn("rollback", batch.calls)

    def test_login_failure_never_builds_or_changes_services(self):
        batch, code = self.run_batch("preflight")
        self.assertEqual(code, 1)
        self.assertEqual(batch.calls, ["cleanup temporary"])

    def test_partial_backend_data_and_sse_failures_trigger_recovery(self):
        for failure in ("backend", "data", "sse"):
            batch, code = self.run_batch(failure)
            self.assertEqual(code, 1)
            self.assertIn("rollback", batch.calls)

    def test_unavailable_certificate_retains_healthy_closed_signup_backend(self):
        batch, code = self.run_batch("pending")
        self.assertEqual(code, 2)
        self.assertTrue(batch.backend_ready)
        self.assertNotIn("rollback", batch.calls)
        self.assertNotIn("chat", batch.calls)

    def test_wrong_gateway_is_never_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Public(Path(folder), Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.images = {"backend":"new", "gateway":"gateway"}
            with patch.object(batch, "inspect", return_value={"project":"foreign", "service":"gateway", "image":"gateway", "id":"foreign"}), \
                 patch.object(batch, "docker") as docker:
                with self.assertRaises(app.Failed): batch.rollback_backend()
                docker.assert_not_called()

    def test_missing_partial_backend_can_be_recreated_during_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = app.Public(Path(folder), Path(folder), "140.113.135.113")
            self.addCleanup(batch.session.close)
            batch.changed = True
            with patch.object(batch, "inspect", return_value=None), patch.object(batch, "docker") as docker, \
                 patch.object(batch, "wait_backend"), patch.object(batch, "verify_existing"), redirect_stdout(io.StringIO()):
                batch.rollback_backend()
                self.assertIn("backend", docker.call_args.args)
                self.assertTrue(batch.report["rollback_verified"])


if __name__ == "__main__":
    unittest.main()
