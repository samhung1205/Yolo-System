#!/usr/bin/env python3
"""
Component-level evaluation harness for the ``explain_detection`` agent flow.

Phase 6A-5. This is a *component* eval, NOT a YOLO model-accuracy eval:

* It uses synthetic, structured detection results (see
  ``explain_detection_cases.jsonl``); no real images and no YOLO inference.
* It exercises the exact production code path that turns structured YOLO data
  into an LLM prompt:
      aggregate_detection_stats(detail)          # app.agents.tools.detection_tools
      -> build_yolo_explainer_messages(msg, ...) # app.agents.subagents
      -> get_chat_model(provider).invoke(msgs)   # app.agents.llm
* It then scores the produced natural-language answer with deterministic
  metrics that check whether the explanation faithfully reflects the
  structured data.

The default provider is ``mock`` so the eval is deterministic and needs no API
key. Pass ``--provider openai`` (etc.) to evaluate a real LLM. The optional
``--use-llm-judge`` flag adds an LLM-as-judge score using the rubric in
``docs/evals/explain_detection_eval_framework.md``; it degrades gracefully to a
no-op when no real provider is configured, so the script never fails for lack
of an API key.

Usage:
    python tests/evals/evaluate_explain_detection.py
    python tests/evals/evaluate_explain_detection.py --provider openai
    python tests/evals/evaluate_explain_detection.py --use-llm-judge
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# Path / import setup — reuse production code without a DB.
# --------------------------------------------------------------------------- #
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# pydantic-settings reads ".env" relative to CWD at import time.
# Change to BACKEND_DIR so backend/.env is found before any app import.
import os as _os
if (_os.getcwd() != str(BACKEND_DIR)) and (BACKEND_DIR / ".env").exists():
    _os.chdir(BACKEND_DIR)

try:
    from app.agents.tools.detection_tools import aggregate_detection_stats  # type: ignore[import]
    from app.agents.subagents import build_yolo_explainer_messages  # type: ignore[import]
    from app.agents.llm import get_chat_model  # type: ignore[import]
except Exception as exc:  # pragma: no cover - import diagnostics
    print(
        "[fatal] could not import backend agent modules.\n"
        f"        Make sure backend dependencies are installed and that\n"
        f"        {BACKEND_DIR} is importable.\n"
        f"        Underlying error: {exc}",
        file=sys.stderr,
    )
    raise

# --------------------------------------------------------------------------- #
# Configuration constants.
# --------------------------------------------------------------------------- #
CASES_FILE = THIS_DIR / "explain_detection_cases.jsonl"
RESULTS_DIR = THIS_DIR / "results"
SUMMARY_JSON = RESULTS_DIR / "explain_detection_eval_summary.json"
REPORT_MD = RESULTS_DIR / "explain_detection_eval_report.md"

# COCO-80 class list (yolo11n.pt / yolov8n.pt default).
# These are added to global_class_vocab so the fabrication check can catch
# any class the LLM invents that the model CAN detect but wasn't in this
# particular detection result. Custom-model classes are added via --class-file.
COCO_80_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

# A detection is treated as "low confidence" when its confidence is strictly
# below this threshold. Boundary cases (0.49 / 0.50 / 0.51) probe this rule.
LOW_CONF_THRESHOLD = 0.50

# Tolerance when matching confidence-shaped numbers cited in the answer text
# against the ground-truth values (accounts for rounding to 2 dp and
# percentage <-> fraction conversion).
CONF_MATCH_TOL = 0.02

# Keyword banks (English + 中文) used by the text-based deterministic checks.
LOW_CONF_KEYWORDS = [
    "low confidence", "low-confidence", "lower confidence", "not confident",
    "uncertain", "unreliable", "below threshold", "weak detection",
    "低信心", "低置信", "信心較低", "信心偏低", "信心不足", "置信度低",
    "置信度較低", "不確定", "偏低", "較不可靠", "低於門檻", "低於閾值",
]
REVIEW_KEYWORDS = [
    "human review", "manual review", "manual check", "manual verification",
    "human verification", "double-check", "double check", "verify", "verified",
    "human", "reviewed by a person", "expert review",
    "人工審查", "人工檢查", "人工確認", "人工複核", "人工複查", "人工核對",
    "人工判讀", "人工判斷", "人工驗證", "建議複查", "建議複核", "建議審核",
    "建議人工", "進一步確認", "再次確認", "審慎", "由人員確認", "人員複核",
]
PREDICTION_KEYWORDS = [
    "yolo", "predict", "prediction", "detected", "detection", "model",
    "estimate", "estimated", "likely", "may be", "possible",
    "偵測", "預測", "推論", "模型", "可能", "疑似", "估計",
]
# Words that imply invented visual/appearance detail not present in structured
# data (which only has class, confidence and bbox coordinates).
# Precision rules:
# - "background" is fine in technical context ("background influence"), only
#   flag "background is" / "背景是" (describing the actual scene).
# - Bare colour adjectives are fine as modifiers for class names the model
#   CAN detect ("red car" is not fabricating a class); flag colour claims about
#   people's clothing / scene appearance ("wearing a red shirt", "紅色衣服").
# - Position words from bbox coordinates are acceptable ("upper-left area"),
#   but invented scene layout ("standing next to a tree") is not.
VISUAL_DETAIL_KEYWORDS = [
    "wearing a", "wearing the", "wearing red", "wearing blue", "wearing green",
    "wearing yellow", "wearing white", "wearing black",
    "shirt", "jacket", "dress", "outfit",
    "sunny", "cloudy", "rainy", "outdoor scene", "indoor scene",
    "smiling", "facial expression", "looking at",
    "background is", "background appears", "background color",
    "background shows", "next to a tree", "standing on grass",
    "穿著", "穿紅", "穿白", "穿黑", "穿藍", "穿黃",
    "衣服顏色", "服裝", "笑容", "表情", "正在微笑",
    "背景是", "背景顏色", "背景為", "背景有",
    "天氣晴", "天氣陰", "晴天", "陰天", "戶外場景", "室內場景",
]
# Chinese translations for COCO class names — used by the class-count fidelity
# check so that an LLM responding in Chinese is not penalised for translating
# class names correctly (e.g. "traffic light" → "紅綠燈").
# Keyed by the English class name (lowercase).
COCO_CLASS_ZH: dict[str, list[str]] = {
    "person": ["人", "行人", "人員", "人物"],
    "bicycle": ["腳踏車", "自行車", "單車", "腳踏"],
    "car": ["車", "汽車", "轎車", "小客車", "車輛"],
    "motorcycle": ["機車", "摩托車", "重機"],
    "airplane": ["飛機", "航班"],
    "bus": ["公車", "巴士", "公共汽車"],
    "train": ["火車", "列車"],
    "truck": ["卡車", "貨車", "貨卡"],
    "boat": ["船", "船隻", "小船"],
    "traffic light": ["紅綠燈", "交通號誌", "號誌燈", "信號燈"],
    "fire hydrant": ["消防栓", "消火栓"],
    "stop sign": ["停車標誌", "停車牌", "stop"],
    "bench": ["長椅", "椅子", "板凳"],
    "bird": ["鳥", "鳥類"],
    "cat": ["貓", "貓咪", "貓科"],
    "dog": ["狗", "狗狗", "犬", "小狗"],
    "horse": ["馬", "馬匹"],
    "sheep": ["羊", "綿羊"],
    "cow": ["牛", "乳牛", "牛隻"],
    "elephant": ["象", "大象"],
    "bear": ["熊", "熊科"],
    "zebra": ["斑馬"],
    "giraffe": ["長頸鹿"],
    "backpack": ["背包", "後背包", "書包"],
    "umbrella": ["雨傘", "傘"],
    "handbag": ["手提包", "手袋"],
    "tie": ["領帶"],
    "suitcase": ["行李箱", "行李"],
    "frisbee": ["飛盤"],
    "surfboard": ["衝浪板"],
    "kite": ["風箏"],
    "laptop": ["筆電", "筆記型電腦", "電腦"],
    "cell phone": ["手機", "手機", "行動電話", "智慧型手機"],
    "bottle": ["瓶子", "水瓶", "瓶"],
    "cup": ["杯子", "杯"],
    "chair": ["椅子", "椅"],
    "couch": ["沙發", "沙發椅"],
    "bed": ["床", "床鋪"],
    "clock": ["時鐘", "鐘", "鐘錶"],
    "vase": ["花瓶"],
}

ZERO_OBJECT_KEYWORDS = [
    "no object", "no objects", "zero object", "nothing was detected",
    "did not detect", "no detection", "none detected", "0 object",
    "沒有偵測", "未偵測", "無物件", "沒有物件", "沒有任何", "未發現", "無偵測",
]


# --------------------------------------------------------------------------- #
# LLM-as-Judge rubric (mirrors docs/evals/explain_detection_eval_framework.md).
# --------------------------------------------------------------------------- #
JUDGE_RUBRIC = """
You are evaluating an "explain_detection" agent for a YOLO object-detection
platform. You are given: (a) the STRUCTURED detection data (objects, class_name,
confidence, bbox, model_name, inference_ms, source_type, image size, status),
and (b) the agent's NATURAL-LANGUAGE explanation.

Score the explanation on FAITHFUL, APPROPRIATELY-HEDGED GROUNDING.

Use this rubric:
- 5: Every object/class/count/confidence in the text matches the structured
     data exactly. It frames results as YOLO *predictions*, not ground truth.
     It explicitly mentions the lowest-confidence detection(s) and recommends
     human review when confidence is low or results are ambiguous. Includes
     model_name, inference_ms, and total count. Invents nothing.
- 3: Mostly grounded and correct on counts/classes, but has ONE material gap
     (omits low-confidence detection, OR drops model_name/inference_ms, OR
     states a prediction as fact once), while inventing no new objects/numbers.
- 1: Fabricates objects, classes, confidence values, bboxes, or visual details;
     OR states predictions as certain fact throughout; OR gives a generic answer
     ignoring this detection; OR never flags low confidence when the data
     clearly warrants human review.

Output ONLY a JSON object:
{"score": <1-5>, "justification": "<one sentence>", "unsupported_claims": ["<verbatim quote>", ...]}
""".strip()


# --------------------------------------------------------------------------- #
# Ground-truth derivation (single source of truth: the detection objects).
# --------------------------------------------------------------------------- #
def derive_ground_truth(detection: dict[str, Any]) -> dict[str, Any]:
    objects = detection.get("objects") or []
    class_counts: dict[str, int] = {}
    confidences: list[float] = []
    for obj in objects:
        class_counts[obj["class_name"]] = class_counts.get(obj["class_name"], 0) + 1
        confidences.append(round(float(obj["confidence"]), 4))

    status = (detection.get("status") or "").lower()
    low_conf_values = [c for c in confidences if c < LOW_CONF_THRESHOLD]
    low_confidence_present = len(low_conf_values) > 0
    # Review policy: recommend human review when the run failed/partial, or when
    # any detection is below the confidence threshold. A clean completed run
    # (including a completed zero-object run) does not require review.
    should_recommend_review = (
        status in {"failed", "partial"} or low_confidence_present
    )

    return {
        "total_count": len(objects),
        "class_counts": class_counts,
        "confidences": confidences,
        "low_conf_values": low_conf_values,
        "low_confidence_present": low_confidence_present,
        "should_recommend_review": should_recommend_review,
        "status": status,
        "model_name": detection.get("model_name"),
        "inference_ms": detection.get("inference_ms"),
        "source_type": (detection.get("source_type") or "").lower(),
    }


# --------------------------------------------------------------------------- #
# Text parsing helpers.
# --------------------------------------------------------------------------- #
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?%?)")


def _extract_confidence_candidates(text: str) -> list[float]:
    """Return every confidence-shaped number cited in ``text`` as a fraction.

    A token counts as confidence-shaped if it is a percentage (``87%``) or a
    decimal whose value is within [0, 1] (``0.87``). Plain integers (counts,
    inference_ms) and values > 1 (bbox / image dimensions) are ignored.

    Numbers followed by time units (秒, s, ms, 毫秒) or preceded by time
    context words are excluded — e.g. "0.04 秒" (= 40 ms / 1000) must not be
    treated as a confidence value.
    """
    # Suffixes that unambiguously mark a time value, not a confidence.
    _TIME_SUFFIX_RE = re.compile(
        r"(\d+(?:\.\d+)?)\s*(?:秒|毫秒|ms\b|milliseconds?)",
        re.IGNORECASE,
    )
    time_values: set[str] = {m.group(1) for m in _TIME_SUFFIX_RE.finditer(text)}

    candidates: list[float] = []
    for token in _NUMBER_RE.findall(text):
        if token in time_values:
            continue  # skip inference-time numbers expressed in seconds
        if token.endswith("%"):
            try:
                val = float(token[:-1]) / 100.0
            except ValueError:
                continue
            if 0.0 <= val <= 1.0:
                candidates.append(round(val, 4))
        elif "." in token:
            try:
                val = float(token)
            except ValueError:
                continue
            if 0.0 <= val <= 1.0:
                candidates.append(round(val, 4))
    return candidates


def _contains_number(text: str, number: int | float) -> bool:
    """True if ``number`` appears in ``text`` as a standalone token."""
    pattern = rf"(?<!\d){re.escape(str(number))}(?!\d)"
    return re.search(pattern, text) is not None


def _contains_any(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


# Negation words that precede a review keyword and negate its meaning.
_REVIEW_NEGATIONS = [
    "無需", "不需", "不必", "不用", "無須", "不建議", "沒有必要", "毋需",
    "no need", "not needed", "not required", "not necessary",
    "not recommended", "don't need", "do not need", "unnecessary",
    "without needing", "n't need",
]


def _contains_review_recommendation(text: str) -> bool:
    """True if the text actively recommends human review.

    Excludes negated mentions like "無需人工複查" (no review needed) and
    "not necessary to review" so that a model correctly saying review is
    unnecessary is not penalised as an over-trigger.
    """
    low = text.lower()
    for kw in REVIEW_KEYWORDS:
        kw_low = kw.lower()
        idx = 0
        while True:
            pos = low.find(kw_low, idx)
            if pos == -1:
                break
            # Check a window of up to 20 chars before the keyword for negation.
            prefix = low[max(0, pos - 20): pos]
            if not any(neg.lower() in prefix for neg in _REVIEW_NEGATIONS):
                return True
            idx = pos + 1
    return False


def _class_count_mentioned(text: str, class_name: str, count: int, window: int = 40) -> bool:
    """Heuristic: the ``count`` appears near a mention of ``class_name``.

    Checks both the English class name and its Chinese aliases (from
    ``COCO_CLASS_ZH``) so that correct Chinese translations are not penalised.
    """
    count_re = re.compile(rf"(?<!\d){count}(?!\d)")
    # Build the list of names to search for.
    aliases = [class_name.lower()] + [a.lower() for a in COCO_CLASS_ZH.get(class_name.lower(), [])]
    text_low = text.lower()
    for name in aliases:
        for m in re.finditer(re.escape(name), text_low):
            start = max(0, m.start() - window)
            end = min(len(text_low), m.end() + window)
            if count_re.search(text_low[start:end]):
                return True
    return False


# --------------------------------------------------------------------------- #
# Deterministic metric evaluation for a single case.
# --------------------------------------------------------------------------- #
def evaluate_case(
    text: str,
    gt: dict[str, Any],
    global_class_vocab: set[str],
) -> dict[str, Any]:
    total = gt["total_count"]
    class_counts = gt["class_counts"]
    confidences = gt["confidences"]

    # -- total-count present ------------------------------------------------- #
    if total == 0:
        total_count_present = _contains_number(text, 0) or _contains_any(text, ZERO_OBJECT_KEYWORDS)
    else:
        total_count_present = _contains_number(text, total)

    # -- class-count fidelity ------------------------------------------------ #
    if total == 0:
        # No classes to enumerate; fidelity == correctly conveying "zero".
        class_fidelity = total_count_present
        per_class_pass = {}
    else:
        per_class_pass = {
            cls: _class_count_mentioned(text, cls, cnt)
            for cls, cnt in class_counts.items()
        }
        class_fidelity = total_count_present and all(per_class_pass.values())

    # -- confidence-value accuracy (no fabricated numbers) ------------------- #
    allowed = {round(c, 2) for c in confidences}
    if confidences:
        allowed.add(round(min(confidences), 2))
        allowed.add(round(max(confidences), 2))
        allowed.add(round(sum(confidences) / len(confidences), 2))
    allowed.add(round(LOW_CONF_THRESHOLD, 2))  # threshold is legitimate to cite
    cited = _extract_confidence_candidates(text)
    fabricated_conf = [
        c for c in cited
        if not any(abs(c - a) <= CONF_MATCH_TOL for a in allowed)
    ]
    confidence_accuracy = len(fabricated_conf) == 0
    # Whether any real confidence value is actually cited (used for judging
    # low-confidence mentions and grounding).
    cited_real_conf = [
        c for c in cited
        if any(abs(c - round(v, 2)) <= CONF_MATCH_TOL for v in confidences)
    ]

    # -- metadata coverage --------------------------------------------------- #
    meta_fields: dict[str, Optional[bool]] = {}
    # model_name
    if gt["model_name"]:
        meta_fields["model_name"] = str(gt["model_name"]).lower() in text.lower()
    else:
        meta_fields["model_name"] = None  # not applicable
    # inference_ms
    if gt["inference_ms"] is not None:
        meta_fields["inference_ms"] = _contains_number(text, gt["inference_ms"])
    else:
        meta_fields["inference_ms"] = None
    # source_type
    st = gt["source_type"]
    st_synonyms = {
        "image": ["image", "圖片", "圖像", "影像", "照片"],
        "video": ["video", "影片", "視訊", "錄影"],
        "realtime": ["realtime", "real-time", "即時", "實時", "webcam", "攝影機"],
    }.get(st, [st] if st else [])
    meta_fields["source_type"] = _contains_any(text, st_synonyms) if st else None
    # status
    status = gt["status"]
    status_synonyms = {
        "completed": ["completed", "complete", "成功", "完成"],
        "failed": ["failed", "failure", "失敗", "錯誤"],
        "partial": ["partial", "incomplete", "部分", "未完成", "中斷"],
    }.get(status, [status] if status else [])
    meta_fields["status"] = _contains_any(text, status_synonyms) if status else None
    # total_count as a metadata field too
    meta_fields["total_count"] = total_count_present

    applicable = {k: v for k, v in meta_fields.items() if v is not None}
    metadata_coverage = (
        sum(1 for v in applicable.values() if v) / len(applicable)
        if applicable else 0.0
    )
    # Strict "core" metadata coverage: model_name + inference_ms + total_count
    # (only over the applicable ones for this case).
    core_keys = ["model_name", "inference_ms", "total_count"]
    core_applicable = [meta_fields[k] for k in core_keys if meta_fields[k] is not None]
    metadata_core_ok = all(core_applicable) if core_applicable else False

    # -- low-confidence mention --------------------------------------------- #
    low_conf_mentioned = _contains_any(text, LOW_CONF_KEYWORDS) or (
        bool(gt["low_conf_values"]) and any(
            _contains_number(text, round(v, 2)) for v in gt["low_conf_values"]
        )
    )

    # -- human-review trigger ------------------------------------------------ #
    review_recommended = _contains_review_recommendation(text)

    # -- fabricated class (invented object from the controlled vocabulary) --- #
    present_classes = {c.lower() for c in class_counts}
    fabricated_classes = [
        cls for cls in global_class_vocab
        if cls not in present_classes and re.search(rf"\b{re.escape(cls)}\b", text.lower())
    ]

    # -- invented visual detail --------------------------------------------- #
    invented_visual = _contains_any(text, VISUAL_DETAIL_KEYWORDS)

    # -- prediction framing (avoids stating predictions as ground truth) ----- #
    prediction_framing = _contains_any(text, PREDICTION_KEYWORDS)

    # -- status acknowledgement for failed/partial --------------------------- #
    if status in {"failed", "partial"}:
        status_acknowledged = bool(meta_fields.get("status"))
    else:
        status_acknowledged = True

    # -- grounding (composite pass/fail) ------------------------------------- #
    grounding_pass = (
        confidence_accuracy
        and class_fidelity
        and total_count_present
        and not fabricated_classes
        and not invented_visual
        and status_acknowledged
    )

    return {
        "total_count_present": total_count_present,
        "class_fidelity": class_fidelity,
        "per_class_pass": per_class_pass,
        "confidence_accuracy": confidence_accuracy,
        "fabricated_confidence": fabricated_conf,
        "cited_real_confidence": cited_real_conf,
        "metadata_fields": meta_fields,
        "metadata_coverage": metadata_coverage,
        "metadata_core_ok": metadata_core_ok,
        "low_conf_mentioned": low_conf_mentioned,
        "review_recommended": review_recommended,
        "fabricated_classes": fabricated_classes,
        "invented_visual_detail": invented_visual,
        "prediction_framing": prediction_framing,
        "status_acknowledged": status_acknowledged,
        "grounding_pass": grounding_pass,
    }


# --------------------------------------------------------------------------- #
# Optional LLM-as-Judge.
# --------------------------------------------------------------------------- #
def run_llm_judge(judge_model, payload: dict[str, Any], answer: str) -> dict[str, Any]:
    """Return a judge result dict; never raises."""
    try:
        structured = json.dumps(payload, ensure_ascii=False, indent=2)
        messages = [
            {"role": "system", "content": JUDGE_RUBRIC},
            {
                "role": "user",
                "content": (
                    "STRUCTURED DETECTION DATA:\n"
                    f"{structured}\n\n"
                    "AGENT EXPLANATION:\n"
                    f"{answer}\n\n"
                    "Return only the JSON object described in the rubric."
                ),
            },
        ]
        response = judge_model.invoke(messages)
        content = (response.content or "").strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {"score": None, "justification": "unparseable judge output", "raw": content[:500]}
        parsed = json.loads(match.group(0))
        return {
            "score": parsed.get("score"),
            "justification": parsed.get("justification", ""),
            "unsupported_claims": parsed.get("unsupported_claims", []),
        }
    except Exception as exc:  # never fail the eval because of the judge
        return {"score": None, "justification": f"judge error: {exc}"}


# --------------------------------------------------------------------------- #
# Aggregation + reporting.
# --------------------------------------------------------------------------- #
def _rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def build_summary(case_rows: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    n = len(case_rows)

    # Denominators for conditional metrics.
    low_conf_cases = [r for r in case_rows if r["gt"]["low_confidence_present"]]
    review_cases = [r for r in case_rows if r["gt"]["should_recommend_review"]]
    no_review_cases = [r for r in case_rows if not r["gt"]["should_recommend_review"]]

    metrics = {
        "metadata_coverage_rate": round(
            sum(r["metrics"]["metadata_coverage"] for r in case_rows) / n, 4
        ) if n else None,
        "metadata_core_coverage_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["metadata_core_ok"]), n
        ),
        "class_count_fidelity_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["class_fidelity"]), n
        ),
        "confidence_value_accuracy_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["confidence_accuracy"]), n
        ),
        "low_confidence_mention_rate": _rate(
            sum(1 for r in low_conf_cases if r["metrics"]["low_conf_mentioned"]),
            len(low_conf_cases),
        ),
        "human_review_trigger_rate": _rate(
            sum(1 for r in review_cases if r["metrics"]["review_recommended"]),
            len(review_cases),
        ),
        "review_over_trigger_rate": _rate(
            sum(1 for r in no_review_cases if r["metrics"]["review_recommended"]),
            len(no_review_cases),
        ),
        "grounding_pass_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["grounding_pass"]), n
        ),
        "fabricated_visual_detail_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["invented_visual_detail"]), n
        ),
        "prediction_framing_rate": _rate(
            sum(1 for r in case_rows if r["metrics"]["prediction_framing"]), n
        ),
    }

    judge_scores = [
        r["judge"]["score"] for r in case_rows
        if r.get("judge") and isinstance(r["judge"].get("score"), (int, float))
    ]
    llm_judge_summary = None
    if meta.get("use_llm_judge"):
        llm_judge_summary = {
            "enabled": True,
            "active": bool(judge_scores),
            "scored_cases": len(judge_scores),
            "avg_score": round(sum(judge_scores) / len(judge_scores), 3) if judge_scores else None,
        }

    return {
        "generated_at": meta["generated_at"],
        "provider": meta["provider"],
        "model_name": meta["model_name"],
        "num_cases": n,
        "low_conf_threshold": LOW_CONF_THRESHOLD,
        "denominators": {
            "all_cases": n,
            "low_confidence_cases": len(low_conf_cases),
            "review_warranted_cases": len(review_cases),
            "review_not_warranted_cases": len(no_review_cases),
        },
        "metrics": metrics,
        "llm_judge": llm_judge_summary,
        "cases": [
            {
                "id": r["id"],
                "category": r["category"],
                "gt": {
                    "total_count": r["gt"]["total_count"],
                    "class_counts": r["gt"]["class_counts"],
                    "low_confidence_present": r["gt"]["low_confidence_present"],
                    "should_recommend_review": r["gt"]["should_recommend_review"],
                    "status": r["gt"]["status"],
                },
                "results": {
                    "metadata_coverage": round(r["metrics"]["metadata_coverage"], 4),
                    "metadata_core_ok": r["metrics"]["metadata_core_ok"],
                    "class_fidelity": r["metrics"]["class_fidelity"],
                    "confidence_accuracy": r["metrics"]["confidence_accuracy"],
                    "fabricated_confidence": r["metrics"]["fabricated_confidence"],
                    "low_conf_mentioned": r["metrics"]["low_conf_mentioned"],
                    "review_recommended": r["metrics"]["review_recommended"],
                    "fabricated_classes": r["metrics"]["fabricated_classes"],
                    "invented_visual_detail": r["metrics"]["invented_visual_detail"],
                    "prediction_framing": r["metrics"]["prediction_framing"],
                    "grounding_pass": r["metrics"]["grounding_pass"],
                },
                "judge": r.get("judge"),
                "answer_excerpt": r["answer"][:400],
            }
            for r in case_rows
        ],
    }


def _fmt_rate(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def build_report_md(summary: dict[str, Any]) -> str:
    m = summary["metrics"]
    lines: list[str] = []
    lines.append("# explain_detection — Component Eval Report")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at']}`")
    lines.append(f"- Provider / model: `{summary['provider']}` / `{summary['model_name']}`")
    lines.append(f"- Cases: **{summary['num_cases']}**")
    lines.append(f"- Low-confidence threshold: `< {summary['low_conf_threshold']}`")
    lines.append("")
    if summary["provider"] == "mock":
        lines.append(
            "> **Note:** provider is `mock`. The mock model echoes the structured "
            "tool payload verbatim, so metrics measure *whether the data is "
            "surfaced*, not genuine reasoning/faithfulness. Run with "
            "`--provider openai` (or another real provider) for a meaningful "
            "faithfulness signal."
        )
        lines.append("")

    lines.append("## Headline metrics")
    lines.append("")
    lines.append("| Metric | Value | Denominator |")
    lines.append("| --- | --- | --- |")
    d = summary["denominators"]
    lines.append(f"| Metadata coverage rate | {_fmt_rate(m['metadata_coverage_rate'])} | {d['all_cases']} cases (field-avg) |")
    lines.append(f"| Metadata core coverage (name+ms+total) | {_fmt_rate(m['metadata_core_coverage_rate'])} | {d['all_cases']} cases |")
    lines.append(f"| Class-count fidelity | {_fmt_rate(m['class_count_fidelity_rate'])} | {d['all_cases']} cases |")
    lines.append(f"| Confidence-value accuracy | {_fmt_rate(m['confidence_value_accuracy_rate'])} | {d['all_cases']} cases |")
    lines.append(f"| Low-confidence mention rate | {_fmt_rate(m['low_confidence_mention_rate'])} | {d['low_confidence_cases']} low-conf cases |")
    lines.append(f"| Human-review trigger rate | {_fmt_rate(m['human_review_trigger_rate'])} | {d['review_warranted_cases']} review-warranted cases |")
    lines.append(f"| Review over-trigger rate | {_fmt_rate(m['review_over_trigger_rate'])} | {d['review_not_warranted_cases']} not-warranted cases |")
    lines.append(f"| Grounding pass rate | {_fmt_rate(m['grounding_pass_rate'])} | {d['all_cases']} cases |")
    lines.append(f"| Fabricated visual-detail rate | {_fmt_rate(m['fabricated_visual_detail_rate'])} | {d['all_cases']} cases (lower is better) |")
    lines.append(f"| Prediction-framing rate | {_fmt_rate(m['prediction_framing_rate'])} | {d['all_cases']} cases |")
    lines.append("")

    if summary.get("llm_judge"):
        lj = summary["llm_judge"]
        lines.append("## LLM-as-Judge")
        lines.append("")
        if lj.get("active"):
            lines.append(f"- Scored cases: {lj['scored_cases']} / {summary['num_cases']}")
            lines.append(f"- Average faithfulness score (1-5): **{lj['avg_score']}**")
        else:
            lines.append(
                "- Enabled but inactive (no real provider / API key available). "
                "Judge was skipped without failing the run."
            )
        lines.append("")

    lines.append("## Per-case results")
    lines.append("")
    lines.append("| Case | Category | Meta | Core | Class | Conf | LowConf | Review | Ground | Judge |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for c in summary["cases"]:
        r = c["results"]
        gt = c["gt"]

        def chk(v: bool) -> str:
            return "PASS" if v else "FAIL"

        low = chk(r["low_conf_mentioned"]) if gt["low_confidence_present"] else "-"
        rev = chk(r["review_recommended"]) if gt["should_recommend_review"] else (
            "OVER" if r["review_recommended"] else "-"
        )
        judge = ""
        if c.get("judge") and c["judge"].get("score") is not None:
            judge = str(c["judge"]["score"])
        lines.append(
            f"| {c['id']} | {c['category']} | {r['metadata_coverage']*100:.0f}% | "
            f"{chk(r['metadata_core_ok'])} | {chk(r['class_fidelity'])} | "
            f"{chk(r['confidence_accuracy'])} | {low} | {rev} | "
            f"{chk(r['grounding_pass'])} | {judge or '-'} |"
        )
    lines.append("")

    lines.append("## Failing cases (grounding)")
    lines.append("")
    failing = [c for c in summary["cases"] if not c["results"]["grounding_pass"]]
    if not failing:
        lines.append("- None. All cases passed the grounding composite.")
    else:
        for c in failing:
            r = c["results"]
            reasons = []
            if not r["class_fidelity"]:
                reasons.append("class-count fidelity")
            if not r["confidence_accuracy"]:
                reasons.append(f"fabricated confidence {r['fabricated_confidence']}")
            if r["fabricated_classes"]:
                reasons.append(f"fabricated classes {r['fabricated_classes']}")
            if r["invented_visual_detail"]:
                reasons.append("invented visual detail")
            lines.append(f"- **{c['id']}** ({c['category']}): {', '.join(reasons) or 'see per-case data'}")
    lines.append("")

    lines.append("## Metric definitions")
    lines.append("")
    lines.append(
        "- **Metadata coverage rate**: per-case fraction of applicable metadata "
        "fields (model_name, inference_ms, source_type, status, total count) "
        "surfaced in the answer, averaged across cases. Fields that are None in "
        "the structured data are excluded from that case's denominator.\n"
        "- **Metadata core coverage**: fraction of cases where model_name, "
        "inference_ms AND total count are all present (only over the applicable "
        "core fields for that case).\n"
        "- **Class-count fidelity**: fraction of cases where the total count is "
        "present AND every class's count appears near its class name (windowed "
        "match). Zero-object cases pass by clearly conveying 'zero/none'.\n"
        "- **Confidence-value accuracy**: fraction of cases where every "
        "confidence-shaped number cited (decimals in [0,1] or percentages) "
        "matches a real confidence / range value / the threshold, within "
        f"±{CONF_MATCH_TOL}. Cases citing no confidence pass (no fabrication).\n"
        "- **Low-confidence mention rate**: among cases with >=1 detection below "
        "the threshold, fraction whose answer flags low confidence (keywords or "
        "citing the low value).\n"
        "- **Human-review trigger rate**: among review-warranted cases "
        "(failed/partial status OR any low-confidence detection), fraction "
        "recommending human review.\n"
        "- **Review over-trigger rate**: among NOT-warranted cases, fraction "
        "that still recommended review (lower is better).\n"
        "- **Grounding pass rate**: composite; a case passes only if confidence "
        "accuracy, class-count fidelity, total-count present, no fabricated "
        "classes, no invented visual detail, and (for failed/partial) status "
        "acknowledgement all hold.\n"
        "- **Fabricated visual-detail rate**: fraction inventing colours / "
        "appearance / scene words absent from the structured data (lower is "
        "better).\n"
        "- **Prediction-framing rate**: fraction framing results as model "
        "predictions (keywords like YOLO/predict/偵測/模型)."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main.
# --------------------------------------------------------------------------- #
def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"[fatal] invalid JSON on line {line_no}: {exc}")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        default="mock",
        help="LLM provider for the system-under-test (default: mock; "
        "options: mock/openai/deepseek/ollama).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model name for the chosen provider.",
    )
    parser.add_argument(
        "--use-llm-judge",
        action="store_true",
        help="Also run the LLM-as-judge rubric (no-op if no real provider).",
    )
    parser.add_argument(
        "--judge-provider",
        default=None,
        help="Provider for the judge model (defaults to --provider).",
    )
    parser.add_argument(
        "--cases",
        default=str(CASES_FILE),
        help="Path to the JSONL cases file.",
    )
    parser.add_argument(
        "--class-file",
        default=None,
        help=(
            "Path to a plain-text file listing one class name per line from "
            "the custom-trained YOLO model. When omitted, COCO-80 is used as "
            "the base class vocabulary."
        ),
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.0,
        help=(
            "Seconds to sleep between LLM calls. Use 7 for OpenAI free tier "
            "(10 RPM limit). Default: 0."
        ),
    )
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    if not cases:
        raise SystemExit("[fatal] no cases found")

    # Build the global class vocabulary: start with COCO-80 (or custom file),
    # then add any classes that appear across the synthetic cases.
    if args.class_file:
        class_file_path = Path(args.class_file)
        if not class_file_path.exists():
            raise SystemExit(f"[fatal] --class-file not found: {class_file_path}")
        custom_classes = [
            line.strip().lower() for line in class_file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        global_class_vocab: set[str] = set(custom_classes)
        print(f"[info] loaded {len(global_class_vocab)} classes from {class_file_path.name}")
    else:
        global_class_vocab: set[str] = {c.lower() for c in COCO_80_CLASSES}
        print(f"[info] using COCO-80 class vocabulary ({len(global_class_vocab)} classes)")

    for case in cases:
        for obj in case["detection"].get("objects") or []:
            global_class_vocab.add(obj["class_name"].lower())

    model = get_chat_model(provider=args.provider, model_name=args.model)
    provider = model.provider
    model_name = getattr(model, "model_name", "")

    judge_model = None
    if args.use_llm_judge:
        judge_model = get_chat_model(provider=args.judge_provider or args.provider)
        if judge_model.provider == "mock":
            print(
                "[warn] --use-llm-judge requested but no real provider/API key is "
                "available; judge will be skipped (scores = null).",
                file=sys.stderr,
            )

    print(f"[info] running {len(cases)} cases with provider={provider} model={model_name}")

    case_rows: list[dict[str, Any]] = []
    for case_idx, case in enumerate(cases):
        detection = case["detection"]
        user_message = case.get("user_message") or "請解釋這筆 YOLO 偵測結果。"

        # Reconstruct the exact 'detail' dict shape that
        # get_detection_detail_tool would emit, then run the production
        # aggregation + message builder (no DB / no YOLO inference).
        objects = detection.get("objects") or []
        detail = {
            "ok": True,
            "detection_id": detection.get("detection_id"),
            "user_id": detection.get("user_id"),
            "source_type": detection.get("source_type"),
            "source_filename": detection.get("source_filename"),
            "model_name": detection.get("model_name"),
            "status": detection.get("status"),
            "inference_ms": detection.get("inference_ms"),
            "image_width": detection.get("image_width"),
            "image_height": detection.get("image_height"),
            "frame_count": detection.get("frame_count"),
            "error_message": detection.get("error_message"),
            "created_at": detection.get("created_at"),
            "object_count": len(objects),
            "objects": objects,
        }
        stats = aggregate_detection_stats(detail)
        payload = {
            "ok": True,
            "detection_id": detection.get("detection_id"),
            "detail": detail,
            "stats": stats,
        }
        messages = build_yolo_explainer_messages(user_message, payload)

        if args.request_delay > 0 and case_idx > 0:
            time.sleep(args.request_delay)

        print(f"[{case_idx+1:02d}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
        try:
            response = model.invoke(messages)
            answer = (response.content or "").strip()
            print("ok")
        except Exception as exc:  # pragma: no cover - defensive
            answer = f"[eval-error] model invocation failed: {exc}"
            print(f"ERR: {exc}")

        gt = derive_ground_truth(detection)
        metrics = evaluate_case(answer, gt, global_class_vocab)

        judge_result = None
        if judge_model is not None and judge_model.provider != "mock":
            judge_result = run_llm_judge(judge_model, payload, answer)

        case_rows.append({
            "id": case["id"],
            "category": case.get("category", ""),
            "gt": gt,
            "metrics": metrics,
            "judge": judge_result,
            "answer": answer,
        })

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model_name": model_name,
        "use_llm_judge": args.use_llm_judge,
    }
    summary = build_summary(case_rows, meta)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(build_report_md(summary), encoding="utf-8")

    # Console summary.
    m = summary["metrics"]
    print("\n=== explain_detection eval summary ===")
    print(f"provider/model      : {provider} / {model_name}")
    print(f"metadata coverage   : {_fmt_rate(m['metadata_coverage_rate'])}")
    print(f"metadata core       : {_fmt_rate(m['metadata_core_coverage_rate'])}")
    print(f"class-count fidelity: {_fmt_rate(m['class_count_fidelity_rate'])}")
    print(f"confidence accuracy : {_fmt_rate(m['confidence_value_accuracy_rate'])}")
    print(f"low-conf mention    : {_fmt_rate(m['low_confidence_mention_rate'])}")
    print(f"human-review trigger: {_fmt_rate(m['human_review_trigger_rate'])}")
    print(f"review over-trigger : {_fmt_rate(m['review_over_trigger_rate'])}")
    print(f"grounding pass rate : {_fmt_rate(m['grounding_pass_rate'])}")
    if summary.get("llm_judge") and summary["llm_judge"].get("active"):
        print(f"llm-judge avg score : {summary['llm_judge']['avg_score']}")
    print(f"\nwrote: {SUMMARY_JSON}")
    print(f"wrote: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
