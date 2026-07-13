# explain_detection — Component Eval Report

- Generated at: `2026-07-08T18:40:16.660987+00:00`
- Provider / model: `deepseek` / `deepseek-chat`
- Cases: **20**
- Low-confidence threshold: `< 0.5`

## Headline metrics

| Metric | Value | Denominator |
| --- | --- | --- |
| Metadata coverage rate | 100.0% | 20 cases (field-avg) |
| Metadata core coverage (name+ms+total) | 100.0% | 20 cases |
| Class-count fidelity | 100.0% | 20 cases |
| Confidence-value accuracy | 100.0% | 20 cases |
| Low-confidence mention rate | 100.0% | 7 low-conf cases |
| Human-review trigger rate | 100.0% | 8 review-warranted cases |
| Review over-trigger rate | 8.3% | 12 not-warranted cases |
| Grounding pass rate | 100.0% | 20 cases |
| Fabricated visual-detail rate | 0.0% | 20 cases (lower is better) |
| Prediction-framing rate | 100.0% | 20 cases |

## Per-case results

| Case | Category | Meta | Core | Class | Conf | LowConf | Review | Ground | Judge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_01_normal_high_conf | normal_high_confidence | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_02_low_conf_single | low_confidence | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_03_zero_object_image | zero_object | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_04_failed_status | failed_status | 100% | PASS | PASS | PASS | - | PASS | PASS | - |
| case_05_partial_video | partial_status | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_06_multiple_classes | multiple_classes | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_07_single_dominant_class | single_dominant_class | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_08_video_source | video_source | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_09_realtime_source | realtime_source | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_10_conf_boundary_049 | confidence_boundary | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_11_conf_boundary_050 | confidence_boundary | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_12_conf_boundary_051 | confidence_boundary | 100% | PASS | PASS | PASS | - | OVER | PASS | - |
| case_13_missing_metadata | missing_metadata | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_14_unusual_class_combo | unusual_class_combination | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_15_mixed_high_low_conf | mixed_confidence | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_16_many_low_conf | many_low_confidence | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_17_video_low_conf | video_low_confidence | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_18_realtime_zero | realtime_zero_object | 100% | PASS | PASS | PASS | - | - | PASS | - |
| case_19_partial_video_missing_ms | partial_missing_metadata | 100% | PASS | PASS | PASS | PASS | PASS | PASS | - |
| case_20_high_conf_many_classes | high_confidence_many_classes | 100% | PASS | PASS | PASS | - | - | PASS | - |

## Failing cases (grounding)

- None. All cases passed the grounding composite.

## Metric definitions

- **Metadata coverage rate**: per-case fraction of applicable metadata fields (model_name, inference_ms, source_type, status, total count) surfaced in the answer, averaged across cases. Fields that are None in the structured data are excluded from that case's denominator.
- **Metadata core coverage**: fraction of cases where model_name, inference_ms AND total count are all present (only over the applicable core fields for that case).
- **Class-count fidelity**: fraction of cases where the total count is present AND every class's count appears near its class name (windowed match). Zero-object cases pass by clearly conveying 'zero/none'.
- **Confidence-value accuracy**: fraction of cases where every confidence-shaped number cited (decimals in [0,1] or percentages) matches a real confidence / range value / the threshold, within ±0.02. Cases citing no confidence pass (no fabrication).
- **Low-confidence mention rate**: among cases with >=1 detection below the threshold, fraction whose answer flags low confidence (keywords or citing the low value).
- **Human-review trigger rate**: among review-warranted cases (failed/partial status OR any low-confidence detection), fraction recommending human review.
- **Review over-trigger rate**: among NOT-warranted cases, fraction that still recommended review (lower is better).
- **Grounding pass rate**: composite; a case passes only if confidence accuracy, class-count fidelity, total-count present, no fabricated classes, no invented visual detail, and (for failed/partial) status acknowledgement all hold.
- **Fabricated visual-detail rate**: fraction inventing colours / appearance / scene words absent from the structured data (lower is better).
- **Prediction-framing rate**: fraction framing results as model predictions (keywords like YOLO/predict/偵測/模型).
