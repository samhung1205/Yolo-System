The user pasted a dense, complete answer — skipping the interview per the prompt's rules. Here's the eval framework, diagnosis only, no code or docs touched.

## Eval Framework: `explain_detection` (AI Detection Analyst)

**So your agent does:** takes a user request + `detection_id`, retrieves structured YOLO results (metadata, objects, class names, confidence, bboxes, inference time), and produces a natural-language explanation. **Failure modes you named:** overstating predictions as fact, omitting low-confidence detections, inventing visual details, dropping metadata, giving generic answers, and failing to recommend human review. That's what this framework is built around — nothing generic added.

### Three-Dimension Matrix

| Component vs End-to-End | Objective vs Subjective | Quantitative vs Qualitative | Suggested Metrics |
|-------------------------|------------------------|----------------------------|-------------------|
| Component | Objective | Quantitative | **Metadata coverage rate**: % of traces where model_name, inference_ms, and total detection count all appear correctly. **Class-count fidelity**: % where per-class counts in the text exactly match the structured objects. **Confidence-value accuracy**: % where every numeric confidence cited matches the source (no invented numbers). |
| Component | Objective | Qualitative | **Fabrication log**: catalog of invented objects/classes/bboxes/visual details not in source. **Metadata-omission patterns**: which fields get dropped most (e.g. inference_ms always missing). |
| Component | Subjective | Quantitative | **Low-confidence mention rate**: % of traces containing ≥1 sub-threshold detection where the agent flags it (LLM-judge boolean → rate). **Human-review-trigger rate**: % of ambiguous/low-conf traces that recommend review. |
| Component | Subjective | Qualitative | **Epistemic framing quality**: does phrasing treat YOLO as prediction vs ground truth ("YOLO detected" vs "there is a...")? Cluster the failure phrasings. **Uncertainty-explanation depth**: is "suspicious/uncertain" explained or just labeled? |
| End-to-End | Objective | Quantitative | **Grounding rate**: % of full responses with zero unsupported claims (a response passes only if class-count, confidence, metadata, and fabrication checks all pass). **Answer-specificity rate**: % citing the actual `detection_id` data vs generic filler. |
| End-to-End | Subjective | Qualitative | **Overall trustworthiness read**: would a domain user trust and act on this? Where do they get misled or confused? (This is the 20-trace checklist below.) |

No cell is N/A here — every failure mode you listed maps to at least one. (Note: none of these apply to latency/cost, which you didn't raise; skipped deliberately rather than force-fit.)

### LLM-as-Judge Rubric (draft)

The most important subjective metric is **Faithful, appropriately-hedged grounding** — it captures four of your six failure modes (overstating, inventing, omitting low-confidence, missing review recommendation).

```
You are evaluating an "explain_detection" agent for a YOLO object-detection
platform. You are given: (a) the STRUCTURED detection data (objects, class_name,
confidence, bbox, model_name, inference_ms, source_type, image size, status),
and (b) the agent's NATURAL-LANGUAGE explanation.

Score the explanation on FAITHFUL, APPROPRIATELY-HEDGED GROUNDING.

Use this rubric:
- 5: Every object/class/count/confidence in the text matches the structured
     data exactly. It frames results as YOLO *predictions*, not ground truth
     ("YOLO detected 3 objects with confidence..."). It explicitly mentions the
     lowest-confidence detection(s) and recommends human review when confidence
     is low or results are ambiguous. Includes model_name, inference_ms, and
     total count. Invents nothing.
- 3: Mostly grounded and correct on counts/classes, but has ONE material gap:
     e.g. omits the low-confidence detection, OR drops model_name/inference_ms,
     OR states a prediction as fact once ("there is a person" instead of
     "YOLO predicts a person"), while inventing no new objects or numbers.
- 1: Fabricates objects, classes, confidence values, bboxes, or visual details
     not in the data; OR states predictions as certain fact throughout; OR gives
     a generic answer ignoring this detection_id; OR never flags low confidence
     when the data clearly warrants human review.

Output a JSON object: {"score": <1-5>, "justification": "<one sentence>",
"unsupported_claims": ["<verbatim quote>", ...]}
```

Run this with the structured data injected so the judge can verify against ground truth rather than guessing.

### 20-Trace Manual Error Analysis Checklist

When reading 20 random real traces, mark yes/no for each:

1. **Overstatement**: does the agent state any YOLO prediction as certain fact instead of a prediction? (your failure mode #1)
2. **Low-confidence omission**: is there a sub-threshold detection in the data that the text never mentions? (#2)
3. **Invented visual detail**: does the text describe colors, positions, scene, or appearance not present in the structured data? (#3)
4. **Invented objects/classes**: any class or object named that isn't in `detection_objects`?
5. **Invented numbers**: any confidence value or count that doesn't match source?
6. **Metadata omission**: are model_name, inference_ms, and total detection count all present? Note which is dropped. (#4)
7. **Class-count accuracy**: does the per-class summary match the actual object list? (output requirement #1)
8. **Generic-answer smell**: could this response have been written without reading *this* detection_id? (#5)
9. **Human-review trigger**: when confidence is low or results ambiguous, is review recommended? When it's NOT warranted, does it over-trigger noisily? (#6)
10. **Ground-truth disclaimer**: does it avoid implying YOLO output = reality? (output #4)
11. **Uncertainty explained, not just labeled**: is "suspicious/uncertain" backed by a reason (low conf, tiny bbox, class overlap)?
12. **Empty/zero-detection handling**: when no objects detected, does it say so plainly instead of inventing?
13. **Single dominant class**: does it still note the count rather than just naming the class?
14. **`status` handling**: if status is failed/partial, does the explanation acknowledge it rather than explaining phantom results?
15. **`source_type` correctness**: image vs video vs realtime described accurately?
16. **Confidence granularity**: does it distinguish high vs low bands rather than lumping all as "confident"?
17. **Bbox misuse**: does it invent spatial/location claims from bbox coords beyond what's supported?
18. **Consistency**: do the summary counts at top match any per-object detail later in the response?
19. **Tone/hedging balance**: appropriately cautious without being so hedged it's useless?
20. **Language match**: does it answer in the user's language (e.g. 中文 request → 中文 explanation)?

### Recommended Order of Attack

Instrument these first — prioritizing cells where you already have known failure modes (ground truth to test against):

1. **Grounding rate (End-to-End, Objective, Quantitative)** — first, because it's the composite that catches your three highest-severity modes (overstating, inventing, omitting low-confidence). It's the single number that tells you if the agent is trustworthy at all, and the LLM-Judge rubric above makes it runnable this week.
2. **Metadata coverage + class-count fidelity (Component, Objective, Quantitative)** — second, because these are cheaply machine-verifiable against the structured data (no judge needed — pure string/number comparison), so they give you fast, deterministic regression signals for failure modes #4 and #1.
3. **Human-review-trigger rate (Component, Subjective, Quantitative)** — third, because it's the highest-stakes safety behavior for an inspection platform (#6), but needs the low-confidence ground-truth set assembled first, so it follows the two above.

One reminder: these quantitative rates measure *behavior, not correctness*. An agent can hit 95% "metadata coverage" while the 95% still misframe predictions as fact. Always pair the numbers with the 20-trace qualitative read above — the checklist is what catches what the metrics miss.