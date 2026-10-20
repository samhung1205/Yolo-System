"""Exercise adoption failure recovery without Docker, GPU, DB or network."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_compose_apply.py"
spec = importlib.util.spec_from_file_location("lab_compose_apply", SOURCE)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class Simulated(app.Batch):
    def __init__(self, root, failure=None, managed=False):
        super().__init__(root)
        self.config = root / "private"
        self.config.mkdir(mode=0o700)
        self.failure = failure
        self.fired = False
        self.calls = []
        self.states = {}
        for service in ("backend", "web"):
            self.states["sam-yolo-" + service] = {
                "id": "original-" + service, "image": app.IMAGES[service],
                "running": True, "health": "healthy", "mounts": [],
                "restart": "unless-stopped",
                "network": "host", "user": f"{app.os.getuid()}:{app.os.getgid()}",
                "project": "sam-yolo" if managed else None,
                "service": service if managed else None,
            }
        self.states["sam-yolo-mysql"] = {"id": "original-mysql", "running": True, "mounts": []}

    def inspect(self, name, optional=False):
        if name not in self.states:
            if optional:
                return None
            raise app.Failed("container absent")
        return copy.deepcopy(self.states[name])

    def preflight(self):
        self.original = {s: self.inspect("sam-yolo-" + s) for s in ("backend", "web")}
        self.database = self.inspect("sam-yolo-mysql")
        self.baseline = {}
        for s in self.original:
            self.report["backups"][s] = "sam-yolo-" + s + "-backup"

    def inject(self, operation, service):
        if self.failure == (operation, service) and not self.fired:
            self.fired = True
            raise app.Failed("simulated failure")

    def docker(self, *args, optional=False):
        self.calls.append(args)
        if args[0] == "stop":
            name = args[-1]
            self.states[name]["running"] = False
            self.inject("stop", name.removeprefix("sam-yolo-"))
        elif args[0] == "rename":
            old, new = args[1:]
            self.inject("rename", old.removeprefix("sam-yolo-"))
            if new in self.states:
                raise app.Failed("name collision")
            self.states[new] = self.states.pop(old)
        elif args[0] == "start":
            self.states[args[1]]["running"] = True
        elif args[0] == "compose":
            service = args[-1]
            new = copy.deepcopy(self.original[service])
            new.update(id="new-" + service, project="sam-yolo", service=service, running=True)
            self.states["sam-yolo-" + service] = new
            # Failure after create exercises ownership-aware rollback.
            self.inject("up", service)
        else:
            raise AssertionError("Unexpected Docker action")
        return ""

    def health(self, port=8080):
        if not self.states["sam-yolo-backend"]["running"]:
            raise app.Failed("backend unavailable")

    def verify_existing(self):
        if self.inspect("sam-yolo-mysql") != self.database:
            raise app.Failed("DB changed")

    def routes_and_gpu(self):
        self.step = "routes and GPU"
        self.inject("gpu", "backend")

    def stream_check(self, agent=False):
        self.step = "SSE"
        self.inject("sse", "agent" if agent else "chat")

    def inventory(self):
        pass


class AdoptionTests(unittest.TestCase):
    def run_batch(self, failure=None, managed=False):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        batch = Simulated(Path(self.folder.name), failure, managed)
        with redirect_stdout(io.StringIO()):
            status = batch.run()
        self.assertFalse(any(c[0] in ("rm", "volume", "system", "prune") for c in batch.calls))
        self.assertEqual(batch.inspect("sam-yolo-mysql"), {"id": "original-mysql", "running": True, "mounts": []})
        report = next((batch.config / "reports").glob("*.json"))
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(report.read_text())["success"], status == 0)
        return batch, status

    def assert_restored(self, batch):
        for service in ("backend", "web"):
            current = batch.inspect("sam-yolo-" + service)
            self.assertEqual(current["id"], "original-" + service)
            self.assertTrue(current["running"])
        self.assertEqual(batch.report["rollback_failed_services"], [])

    def test_success_preserves_stopped_originals(self):
        batch, status = self.run_batch()
        self.assertEqual(status, 0)
        for service in ("backend", "web"):
            self.assertEqual(batch.inspect("sam-yolo-" + service)["project"], "sam-yolo")
            self.assertFalse(batch.inspect(batch.report["backups"][service])["running"])

    def test_stop_failure_restarts_original(self):
        batch, status = self.run_batch(("stop", "backend"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)

    def test_rename_failure_restarts_original(self):
        batch, status = self.run_batch(("rename", "backend"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)

    def test_partial_backend_create_is_preserved_and_original_restored(self):
        batch, status = self.run_batch(("up", "backend"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)
        self.assertTrue(any("backend-failed-" in name for name in batch.states))

    def test_partial_web_create_restores_both_services(self):
        batch, status = self.run_batch(("up", "web"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)

    def test_gpu_failure_restores_both_services(self):
        batch, status = self.run_batch(("gpu", "backend"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)

    def test_sse_failure_restores_both_services(self):
        batch, status = self.run_batch(("sse", "agent"))
        self.assertEqual(status, 1)
        self.assert_restored(batch)

    def test_managed_services_are_not_recreated(self):
        batch, status = self.run_batch(managed=True)
        self.assertEqual(status, 0)
        self.assertEqual(batch.calls, [])

    def test_foreign_replacement_is_not_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulated(Path(folder))
            batch.preflight()
            with redirect_stdout(io.StringIO()):
                batch.adopt("backend")
            batch.states["sam-yolo-backend"].update(id="foreign-id", project="someone-else")
            batch.calls.clear()
            with redirect_stdout(io.StringIO()):
                batch.rollback()
            self.assertEqual(batch.calls, [])
            self.assertEqual(batch.report["rollback_failed_services"], ["backend"])

    def test_modified_compose_image_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulated(Path(folder))
            (batch.config / "compose.env").write_text("# test")
            bad = {"name": "sam-yolo", "services": {"backend": {"image": "other-image", "pull_policy": "never"}, "web": {}}}
            with patch.object(app.sys, "platform", "linux"), patch.object(batch, "docker", return_value=json.dumps(bad)) as docker:
                with self.assertRaises(app.Failed):
                    app.Batch.preflight(batch)
                self.assertEqual(docker.call_count, 1)

    def test_sse_http_200_with_error_event_is_rejected(self):
        class Response:
            headers = {"Content-Type": "text/event-stream"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_lines(self, **kwargs):
                yield 'data: {"type":"error","message":"private-error"}'
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulated(Path(folder))
            groups = type("JSON", (), {"json": lambda self: [{"provider": "ollama", "available": True}]})()
            with patch.object(batch, "request", side_effect=[groups, Response()]):
                with self.assertRaises(app.Failed) as failure:
                    app.Batch.stream_check(batch)
                self.assertNotIn("private-error", str(failure.exception))

    def test_sse_done_requires_a_saved_answer(self):
        class Response:
            headers = {"Content-Type": "text/event-stream"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_lines(self, **kwargs):
                yield 'data: {"type":"chunk","delta":"hello"}'
                yield 'data: {"type":"done","answer":"hello","conversation_id":"test"}'
        def payload(value):
            return type("JSON", (), {"json": lambda self: value})()
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulated(Path(folder))
            replies = [payload([{"provider":"ollama", "available":True}]), Response(), payload({"messages": []})]
            with patch.object(batch, "request", side_effect=replies):
                with self.assertRaises(app.Failed):
                    app.Batch.stream_check(batch)

    def test_signed_media_content_mismatch_is_rejected(self):
        task = {"status":"completed", "model_sha256":"test-hash", "objects":[],
                "source_image_url":"/static/original.png?sig=private&exp=999"}
        def response(data=None, content=b""):
            return type("Response", (), {"json":lambda self:data, "content":content,
                                          "headers":{"X-Content-Type-Options":"nosniff"}})()
        with tempfile.TemporaryDirectory() as folder:
            batch = Simulated(Path(folder))
            replies = [response(task), response(content=b"original"), response(), response(content=b"different")]
            with patch.object(batch, "request", side_effect=replies):
                with self.assertRaises(app.Failed):
                    app.Batch.task_snapshot(batch, 1)


if __name__ == "__main__":
    unittest.main()
