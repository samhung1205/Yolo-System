"""Offline scoring regression: no provider calls or production database."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import evaluate_agent_engines as evaluator


class ScoringTests(unittest.TestCase):
    def score(self, answer):
        case = {"include": [["harbor_1"], ["harbor_2"], ["harbor_3"]],
                "exclude": ["empty_sea"]}
        return evaluator.score(case, "tool_calling", {
            "answer": answer, "calls": [], "errors": [],
        }, None)

    def test_markdown_filenames_are_accepted(self):
        self.assertTrue(all(self.score(r"**harbor\_1.jpg** harbor\_2.jpg harbor\_3.jpg").values()))

    def test_missing_filename_still_fails(self):
        self.assertFalse(self.score(r"harbor\_1.jpg harbor\_2.jpg harbor\_4.jpg")["include[harbor_3]"])

    def test_escaped_forbidden_filename_still_fails(self):
        self.assertFalse(self.score(r"harbor_1 harbor_2 harbor_3 empty\_sea.jpg")["exclude[empty_sea]"])

    def test_saved_answers_rescore_only_the_false_negative(self):
        source_bytes = (evaluator.RESULTS_DIR / "agent_engine_eval_results.json").read_bytes()
        saved = json.loads(source_bytes)
        cases = {c["id"]: c for c in map(json.loads, evaluator.CASES_FILE.read_text().splitlines())}
        session, _ = evaluator.build_world()
        try:
            rows = copy.deepcopy(saved["rows"])
            for row in rows:
                row["checks"] = evaluator.score(cases[row["case"]], row["engine"], row, session)
                row["passed"] = all(row["checks"].values())
            gemma = [r for r in rows if r["engine"] == "tool_calling" and r["model"] == "gemma4"]
            self.assertEqual((sum(r["passed"] for r in gemma), len(gemma)), (32, 32))
            # Compare against the historical checks even after results are corrected.
            original = copy.deepcopy(saved["rows"])
            by_key = {(r["case"], r["engine"], r["model"], r["attempt"]): r for r in original}
            for entry in saved.get("rescore_history", []):
                for change in entry["changes"]:
                    row = by_key[tuple(change[k] for k in ("case", "engine", "model", "attempt"))]
                    row.update(checks=change["previous_checks"], passed=change["previous_passed"])
            changed = [(a, b) for a, b in zip(original, rows) if a["checks"] != b["checks"]]
            self.assertEqual(len(changed), 1)
            old, new = changed[0]
            self.assertEqual((new["case"], new["engine"], new["model"]),
                             ("batch_class_images", "tool_calling", "gemma4"))
            self.assertEqual(sum(not v for v in old["checks"].values()), 3)
            self.assertTrue(new["passed"])
            for old, new in zip(saved["rows"], rows):
                for key in ("answer", "calls", "errors", "seconds"):
                    self.assertEqual(old[key], new[key])
            with tempfile.TemporaryDirectory() as folder, patch.object(evaluator, "RESULTS_DIR", Path(folder)):
                evaluator.write_report(rows, SimpleNamespace(provider=saved["provider"], repeat=2),
                                       source=saved, source_sha256=hashlib.sha256(source_bytes).hexdigest())
                result = json.loads((Path(folder) / "agent_engine_eval_results.json").read_text())
                self.assertEqual(result["generated_at"], saved["generated_at"])
                self.assertTrue(result["rescore_history"])
                self.assertFalse(result["rescore_history"][-1]["new_model_calls"])
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
