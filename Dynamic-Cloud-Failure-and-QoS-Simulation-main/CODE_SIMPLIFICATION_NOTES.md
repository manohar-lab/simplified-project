# Code Simplification Notes

## What changed

This is a conservative first simplification of the existing project. Only these two implementation files were refactored:

- `src/qos_evaluator.py` — combined the repeated normalization formula into one helper and grouped metric values/weights into small dictionaries.
- `src/recommendation_engine.py` — reduced nested logic while preserving category filtering, unavailable-service exclusion, score ordering, tie-breaking, and explanation messages.

The dashboard, service data, failure simulation, tests, dependencies, and project scope were not changed.

## Why the output should remain the same

- Latency and cost still use lower-is-better normalization.
- Availability and reliability still use higher-is-better normalization.
- Scores remain clamped to 0–1 and rounded to four decimal places.
- Weights are still non-negative and normalized to sum to 1; all-zero weights still fall back to equal weights.
- Unavailable services are still excluded.
- Services are still sorted by descending QoS score, with `service_id` ascending as the tie-breaker.
- The same result fields and explanation text are retained.

## Verification

The test suite was run after these edits:

```text
python -m pytest -q
21 passed
```

This confirms the existing automated tests pass. It does not replace a manual check of the Streamlit dashboard. Run the app and try the same category, weights, and failure actions you use for your demo before presenting it.

## Line-by-line explanation

### `src/qos_evaluator.py`

1. Imports `dataclass` to hold score results and typing helpers for function inputs/outputs.
2. `METRICS` lists the four QoS metrics used by the project.
3. `DEFAULT_WEIGHTS` defines the default importance of each metric.
4. `MetricScores` stores the service ID, four normalized metric scores, and final QoS score.
5. `_normalize()` applies the appropriate formula, handles equal bounds, and clamps the result to 0–1.
6. `normalize_lower_is_better()` is used for latency and cost.
7. `normalize_higher_is_better()` is used for availability and reliability.
8. `validate_and_normalize_weights()` removes negative weights, normalizes the rest to total 1, and uses equal weights if the total is zero.
9. `QoSEvaluator.__init__()` stores the reference ranges used to compare services.
10. `set_reference_bounds()` lets the caller replace those ranges.
11. `evaluate_service()` gathers the service's four metric values, finds their reference bounds, calculates normalized scores, applies weights, and returns `MetricScores`.
12. `evaluate_all()` repeats that calculation for every service and returns a dictionary indexed by service ID.

### `src/recommendation_engine.py`

1. `RecommendationResult` stores the chosen service, its scores, ranked candidates, excluded services, and human-readable explanations.
2. `to_dict()` converts the result to a dictionary suitable for display or other callers.
3. `RecommendationEngine.__init__()` receives the QoS evaluator it will use.
4. `recommend()` first filters services to the requested category.
5. If no category matches, it returns a clear no-candidates result.
6. It separates unavailable services from eligible services.
7. If every candidate is unavailable, it returns a no-eligible-service result.
8. It calculates the QoS score for each eligible service.
9. It sorts by highest score first; if scores tie, the smaller service ID comes first.
10. It builds an explanation showing the selected service and its metric scores.
11. If a previous selection was supplied and the selection changed, it explains whether the old service became unavailable or scored lower.
12. It returns the selected service, ranked list, exclusions, explanation, and status message.

## Important scope note

This project remains a deterministic weighted-QoS simulation. These edits do not add deep reinforcement learning, particle swarm optimization, real cloud APIs, or production cloud orchestration.
