"""Duplicate nosniff values, unchanged media checks and mutation-free resume."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "lab_public_verify.py"
with patch.object(sys, "path", [str(SOURCE.parent)] + sys.path):
    spec = importlib.util.spec_from_file_location("lab_public_verify", SOURCE)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


class HeaderTests(unittest.TestCase):
    def test_single_duplicate_and_case_insensitive_values(self):
        for value in ("nosniff", "nosniff, nosniff", " NoSnIfF , NOSNIFF "):
            self.assertTrue(app.nosniff_values(value))

    def test_missing_conflicting_empty_or_substring_values_fail(self):
        for value in (None, "", "sniff", "nosniff, bad", "bad, nosniff", "nosniff,", "not-nosniff", '"nosniff"'):
            with self.subTest(value=value), self.assertRaises(app.Failed): app.nosniff_values(value)

    def media_case(self, header="nosniff, nosniff", different_signed=False):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        batch = app.Verify(Path(folder.name), "140.113.135.113")
        self.addCleanup(batch.session.close)
        task = {"status":"completed","model_sha256":"model-hash","objects":[],
                "source_image_url":"/static/source.png?sig=test&exp=1", "result_image_url":"/static/result.png?sig=test&exp=1"}
        calls = []
        def request(path, **kwargs):
            calls.append((path, kwargs))
            if path == "/api/detections/1": return SimpleNamespace(json=lambda:task)
            if kwargs.get("expected") == 401: return SimpleNamespace(status_code=401)
            return SimpleNamespace(headers={"X-Content-Type-Options":header},
                                   content=b"different" if different_signed and "?" in path else b"same-image")
        with patch.object(batch,"request",side_effect=request):
            result = batch.task_snapshot(1)
        return batch, result, calls

    def test_duplicates_keep_sha_signed_url_and_unauthenticated_checks(self):
        batch, result, calls = self.media_case()
        self.assertEqual(result["source_image_url"],hashlib.sha256(b"same-image").hexdigest())
        self.assertEqual(len([1 for _,kwargs in calls if kwargs.get("expected")==401]),2)
        signed=[kwargs for path,kwargs in calls if "?" in path]
        self.assertEqual(len(signed),2)
        self.assertTrue(all(kwargs["headers"]=={"Authorization":None} for kwargs in signed))
        self.assertEqual(batch.report["media_nosniff_counts"],[2,2])

    def test_actual_missing_header_and_changed_signed_image_still_fail(self):
        with self.assertRaises(app.Failed): self.media_case(header=None)
        with self.assertRaises(app.Failed): self.media_case(different_signed=True)

    def test_docker_operations_are_limited_to_inspect(self):
        with tempfile.TemporaryDirectory() as folder:
            batch=app.Verify(Path(folder),"140.113.135.113")
            self.addCleanup(batch.session.close)
            with patch.object(app.Repair,"docker",return_value="{}") as docker:
                for operation in ("run","exec","compose","build","stop","start","rm"):
                    with self.subTest(operation=operation),self.assertRaises(app.Failed): batch.docker(operation)
                docker.assert_not_called()
                batch.docker("inspect","sam-yolo-gateway")
                docker.assert_called_once()


class Simulation(app.Verify):
    def __init__(self, root, failure=False):
        super().__init__(root,"140.113.135.113")
        self.work=root / "report"
        self.failure=failure
        self.calls=[]
    def preflight(self):
        self.work.mkdir()
        self.calls.append("HTTPS preflight")
    def acceptance(self):
        self.calls.append("data and SSE acceptance")
        if self.failure: raise app.Failed("login failed")
        self.report["success"]=True
    def unchanged(self): self.calls.append("inspect unchanged")


class WorkflowTests(unittest.TestCase):
    def test_resume_never_calls_gateway_mutation_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            batch=Simulation(Path(folder))
            with patch.object(app.Repair,"prepare",side_effect=AssertionError("must not prepare switch")), \
                 patch.object(app.Repair,"switch",side_effect=AssertionError("must not switch")), \
                 patch.object(app.Repair,"validate_runtime",side_effect=AssertionError("must not run containers")), \
                 redirect_stdout(io.StringIO()):
                result=batch.run()
            self.assertEqual(result,0)
            self.assertEqual(batch.calls,["HTTPS preflight","data and SSE acceptance","inspect unchanged"])
            self.assertTrue(json.loads((batch.work/"report.json").read_text())["success"])

    def test_login_failure_leaves_all_services_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            batch=Simulation(Path(folder),failure=True)
            with patch.object(app.Repair,"rollback",side_effect=AssertionError("must not rollback")),redirect_stdout(io.StringIO()):
                result=batch.run()
            self.assertEqual(result,1)
            self.assertFalse(json.loads((batch.work/"report.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
