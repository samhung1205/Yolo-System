#!/usr/bin/env python3
"""
End-to-end evaluation of the two agent engines (Agent 重構 C).

Compares ``AGENT_ENGINE=pipeline`` (graph.run_graph) and
``AGENT_ENGINE=tool_calling`` (tool_agent.stream_tool_agent) across LLMs on
the same questions.

* Data: a fixed world seeded into an in-memory SQLite database (users,
  detections, objects, one batch). Both engines run the real tool and
  repository code against it — nothing in the agent layer is stubbed.
* Checks follow LangChain's eval guidance — assert on structure, not exact
  text — implemented without extra dependencies:
    - ``expect_tools`` / ``expect_any_tools`` / ``forbid_tools`` / ``expect_args``:
      trajectory checks (like agentevals' "superset" mode); tool-calling
      engine only, since the pipeline does not let the model pick tools.
    - ``include`` (each group: at least one alternative must appear) and
      ``exclude`` (must not appear: other users' data, invented causes).
    - ``check_numbers``: every 0.xx in the answer must be a value of the
      detections in ``data_ids`` (a confidence, min/max/avg overall or per
      class, or a threshold) — catches invented or mis-computed scores.
    - Traditional Chinese: no common Simplified-only characters.
* Nothing is written to the real database and no YOLO inference runs.

Usage (from the repo root, yolo-backend env):
    python tests/evals/evaluate_agent_engines.py                       # ollama qwen2.5,gemma4,llama3.2
    python tests/evals/evaluate_agent_engines.py --models gemma4 --engines tool_calling
    python tests/evals/evaluate_agent_engines.py --provider deepseek --models deepseek-chat   # paid
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
if (BACKEND_DIR / ".env").exists():
    os.chdir(BACKEND_DIR)  # pydantic-settings reads .env from the CWD

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models import DetectionBatch, DetectionObject, DetectionTask, User  # noqa: E402

CASES_FILE = THIS_DIR / "agent_engine_cases.jsonl"
RESULTS_DIR = THIS_DIR / "results"

# Common Simplified-only characters (their Traditional forms differ).
SIMPLIFIED_ONLY = set("们这个为检测识别于体统计录记类么说时对应发现问题结务败历较网络进据显数张飞机处该项视频图车")


# --------------------------------------------------------------------------- #
# Seeded world
# --------------------------------------------------------------------------- #
def _task(task_id, user_id, filename, objects, *, status="completed", source_type="image", batch_id=None, error=None):
    task = DetectionTask(
        id=task_id,
        user_id=user_id,
        batch_id=batch_id,
        source_type=source_type,
        source_filename=filename,
        model_name="yolo11n_asff.pt",
        model_key="seven_class_asff",
        confidence_threshold=0.25,
        iou_threshold=0.45,
        status=status,
        inference_ms=None if status == "failed" else 88.0,
        image_width=1280,
        image_height=720,
        error_message=error,
    )
    task.objects = [
        DetectionObject(
            object_index=index,
            class_id=class_id,
            class_name=name,
            confidence=conf,
            bbox_x1=10.0 + index * 100,
            bbox_y1=20.0,
            bbox_x2=90.0 + index * 100,
            bbox_y2=120.0,
        )
        for index, (class_id, name, conf) in enumerate(objects)
    ]
    return task


def build_world():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    users = {
        "alice": User(id=1, username="alice", nickname="Alice", password_hash="x", is_admin=False, is_active=True),
        "bob": User(id=2, username="bob", nickname="Bob", password_hash="x", is_admin=False, is_active=True),
        "admin": User(id=3, username="admin", nickname="Admin", password_hash="x", is_admin=True, is_active=True),
        "charlie": User(id=4, username="charlie", nickname="Charlie", password_hash="x", is_admin=False, is_active=True),
    }
    session.add_all(users.values())
    session.flush()

    ship, airplane, car, person = (0, "ship"), (1, "airplane"), (2, "car"), (3, "person")
    session.add_all(
        [
            _task(12, 1, "port_a.jpg", [(*ship, 0.91), (*airplane, 0.38), (*ship, 0.77)]),
            _task(13, 1, "open_sea.jpg", []),
            _task(14, 1, "corrupt.jpg", [], status="failed", error="Detection failed due to an internal error"),
            _task(15, 1, "road.mp4", [(*car, 0.81), (*car, 0.66)], source_type="video"),
            _task(16, 1, "port_b.jpg", [(*ship, 0.95), (*ship, 0.9), (*ship, 0.86), (*ship, 0.72), (*ship, 0.61)]),
            _task(20, 2, "street.jpg", [(*person, 0.88)]),
        ]
    )
    batch = DetectionBatch(
        id=3, user_id=1, name="harbor survey", model_name="yolo11n_asff.pt", model_key="seven_class_asff",
        confidence_threshold=0.25, iou_threshold=0.45, status="completed_with_errors",
        total_files=5, processed_count=5, failed_count=1, skipped_files=[],
    )
    session.add(batch)
    session.flush()
    session.add_all(
        [
            _task(30, 1, "harbor_1.jpg", [(*ship, 0.9), (*ship, 0.8)], batch_id=3),
            _task(31, 1, "harbor_2.jpg", [(*ship, 0.7)], batch_id=3),
            _task(32, 1, "harbor_3.jpg", [(*ship, 0.85), (*airplane, 0.55)], batch_id=3),
            _task(33, 1, "empty_sea.jpg", [], batch_id=3),
            _task(34, 1, "broken.jpg", [], status="failed", batch_id=3, error="Detection failed due to an internal error"),
        ]
    )
    session.commit()
    return session, users


GLOBAL_NUMBERS = [0.25, 0.45, 0.5]


def _stats(values: list[float]) -> list[float]:
    return values + [min(values), max(values), sum(values) / len(values)] if values else []


def allowed_numbers(session, task_ids: list[int]) -> list[float]:
    """0.xx values an answer about these detections may quote: each confidence,
    min/max/avg overall and per class, and the thresholds."""
    values = list(GLOBAL_NUMBERS)
    for task in session.query(DetectionTask).filter(DetectionTask.id.in_(task_ids)).all():
        values += _stats([obj.confidence for obj in task.objects])
        for class_name in {obj.class_name for obj in task.objects}:
            values += _stats([obj.confidence for obj in task.objects if obj.class_name == class_name])
    return values


# --------------------------------------------------------------------------- #
# Running one case
# --------------------------------------------------------------------------- #
def _history(case):
    messages = []
    for question, answer in case.get("history", []):
        messages += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
    return messages


def run_case(engine_name, provider, model, case, session, users):
    from app.agents import graph, tool_agent

    kwargs = dict(
        db=session,
        current_user=users[case["user"]],
        message=case["question"],
        history_messages=_history(case),
        conversation_id=f"eval-{case['id']}",
        mode=case["mode"],
        detection_id=case.get("detection_id"),
        batch_id=case.get("batch_id"),
        provider_name=provider,
        model_name_override=model,
    )
    started = time.time()
    calls: list[dict[str, Any]] = []
    if engine_name == "pipeline":
        result = graph.run_graph(**kwargs)
        answer, errors = result["final_answer"], result["errors"]
    else:
        answer, errors = "", []
        for phase, data in tool_agent.stream_tool_agent(**kwargs):
            if phase == "tool" and data["status"] == "running":
                calls.append({"tool": data["tool"], "args": data.get("args") or {}})
            elif phase == "done":
                answer = data["final_answer"]
            elif phase == "error_code":
                errors = [data]
            elif phase == "error":
                answer = data
    return {"answer": answer, "errors": errors, "calls": calls, "seconds": round(time.time() - started, 2)}


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score(case, engine_name, run, session):
    answer = run["answer"] or ""
    lowered = answer.lower()
    checks: dict[str, bool] = {}

    for index, group in enumerate(case.get("include", [])):
        checks[f"include[{'|'.join(group)}]"] = any(option.lower() in lowered for option in group)
    for term in case.get("exclude", []):
        checks[f"exclude[{term}]"] = term.lower() not in lowered

    if case.get("check_numbers"):
        allowed = allowed_numbers(session, case["data_ids"])
        found = [float(x) for x in re.findall(r"(?<![\d.])0\.\d+", answer)]
        invented = [x for x in found if not any(abs(x - a) < 0.0051 for a in allowed)]
        checks["grounded_numbers"] = not invented
        if invented:
            run["invented_numbers"] = invented

    simplified = sorted({ch for ch in answer if ch in SIMPLIFIED_ONLY})
    checks["traditional_chinese"] = not simplified
    if simplified:
        run["simplified_chars"] = "".join(simplified)

    if engine_name == "tool_calling":
        called = {c["tool"] for c in run["calls"]}
        for tool in case.get("expect_tools", []):
            checks[f"tool[{tool}]"] = tool in called
        if case.get("expect_any_tools"):
            checks[f"tool_any[{'|'.join(case['expect_any_tools'])}]"] = bool(called & set(case["expect_any_tools"]))
        for tool in case.get("forbid_tools", []):
            checks[f"no_tool[{tool}]"] = tool not in called
        for tool, expected_args in case.get("expect_args", {}).items():
            checks[f"args[{tool}]"] = any(
                c["tool"] == tool and all(c["args"].get(k) == v for k, v in expected_args.items())
                for c in run["calls"]
            )

    checks["no_engine_error"] = not run["errors"] or case.get("expect_error", False)
    return checks


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def write_report(rows, args):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "agent_engine_eval_results.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "provider": args.provider, "rows": rows},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    combos = sorted({(r["engine"], r["model"]) for r in rows})
    lines = [
        "# Agent engine eval",
        "",
        f"- Generated at: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"- Provider: `{args.provider}` · repeats: {args.repeat} · cases: {len({r['case'] for r in rows})}",
        "- Data: seeded in-memory SQLite world (see `evaluate_agent_engines.py`); real tool code, no YOLO",
        "",
        "## Summary",
        "",
        "| Engine | Model | Cases passed | Checks passed | Grounded numbers | zh-TW | Avg s | Max s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for engine_name, model in combos:
        subset = [r for r in rows if r["engine"] == engine_name and r["model"] == model]
        passed = sum(r["passed"] for r in subset)
        checks = [ok for r in subset for ok in r["checks"].values()]
        grounded = [r["checks"]["grounded_numbers"] for r in subset if "grounded_numbers" in r["checks"]]
        zh = [r["checks"]["traditional_chinese"] for r in subset]
        secs = [r["seconds"] for r in subset]
        lines.append(
            f"| {engine_name} | {model} | {passed}/{len(subset)} | {sum(checks)}/{len(checks)} | "
            f"{sum(grounded)}/{len(grounded)} | {sum(zh)}/{len(zh)} | {statistics.mean(secs):.1f} | {max(secs):.1f} |"
        )

    lines += ["", "## Per case", "", "| Case | " + " | ".join(f"{e} · {m}" for e, m in combos) + " |",
              "|---|" + "---|" * len(combos)]
    for case_id in dict.fromkeys(r["case"] for r in rows):
        cells = []
        for engine_name, model in combos:
            subset = [r for r in rows if r["case"] == case_id and r["engine"] == engine_name and r["model"] == model]
            cells.append(f"{sum(r['passed'] for r in subset)}/{len(subset)}" if subset else "-")
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")

    lines += ["", "## Failures", ""]
    for r in rows:
        if r["passed"]:
            continue
        failed = [name for name, ok in r["checks"].items() if not ok]
        extra = []
        if r.get("invented_numbers"):
            extra.append(f"invented {r['invented_numbers']}")
        if r.get("simplified_chars"):
            extra.append(f"simplified 「{r['simplified_chars']}」")
        tools = ", ".join(f"{c['tool']}{c['args'] or ''}" for c in r["calls"]) or "-"
        answer = (r["answer"] or "").replace("\n", " ")[:220]
        lines.append(f"- **{r['case']}** · {r['engine']} · {r['model']}: failed {failed} {'; '.join(extra)}")
        lines.append(f"  - tools: {tools}")
        lines.append(f"  - answer: {answer}")
    (RESULTS_DIR / "agent_engine_eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines[: lines.index("## Per case")])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--models", default="qwen2.5,gemma4,llama3.2")
    parser.add_argument("--engines", default="pipeline,tool_calling")
    parser.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="re-grade the saved answers in results/agent_engine_eval_results.json with the current cases (no LLM calls)",
    )
    args = parser.parse_args()

    settings.AGENT_ENABLE_VISION = False
    settings.AGENT_ENGINE = "tool_calling"  # only affects use_tool_agent(); engines are called directly here

    cases = [json.loads(line) for line in CASES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    session, users = build_world()
    if args.rescore:
        saved = json.loads((RESULTS_DIR / "agent_engine_eval_results.json").read_text(encoding="utf-8"))
        by_id = {c["id"]: c for c in cases}
        args.provider = saved.get("provider", args.provider)
        rows = []
        for row in saved["rows"]:
            if row["case"] not in by_id:
                continue
            run = {key: row[key] for key in ("answer", "errors", "calls", "seconds")}
            checks = score(by_id[row["case"]], row["engine"], run, session)
            rows.append({**row, **run, "checks": checks, "passed": all(checks.values())})
        args.repeat = max(r["attempt"] for r in rows) + 1
        print(write_report(rows, args))
        return

    rows = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        for engine_name in [e.strip() for e in args.engines.split(",") if e.strip()]:
            for case in cases:
                for attempt in range(args.repeat):
                    run = run_case(engine_name, args.provider, model, case, session, users)
                    checks = score(case, engine_name, run, session)
                    row = {"case": case["id"], "engine": engine_name, "model": model, "attempt": attempt,
                           "passed": all(checks.values()), "checks": checks, **run}
                    rows.append(row)
                    mark = "PASS" if row["passed"] else "FAIL"
                    print(f"{mark} {engine_name:12s} {model:14s} {case['id']:28s} {run['seconds']:5.1f}s", flush=True)
    print()
    print(write_report(rows, args))
    print(f"\nReport: {RESULTS_DIR / 'agent_engine_eval_report.md'}")


if __name__ == "__main__":
    main()
