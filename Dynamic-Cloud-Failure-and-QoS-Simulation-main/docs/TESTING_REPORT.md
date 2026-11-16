# Automated Testing & Verification Report

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Quality Assurance & Test Suite Execution Report  
**Test Suite Framework:** Pytest 9.1.1 with `streamlit.testing.v1.AppTest`  
**Execution Timestamp:** November 16, 2026  
**Final Verdict:** **122 of 122 PASSED (100.0% Pass Rate, 0 Failures, 0 Skipped)**  

---

## 1. Test Environment Specification

The test suite was executed in an isolated local Python virtual environment:
- **Operating System:** Microsoft Windows 11 Enterprise (Build 10.0.26340-SP0, 64-bit)
- **Python Version:** 3.14.3 (tags/v3.14.3:323c59a, MSC v.1944 64-bit AMD64)
- **Pytest Version:** pytest 9.1.1 (pluggy 1.6.0)
- **Test Runner Command:** `python -m pytest tests -v`
- **Execution Wall-Clock Time:** `29.32 seconds`

---

## 2. Test Execution Summary

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Mahendra\Downloads\Dynamic-Cloud-Failure-and-QoS-Simulation-Simplified\Dynamic-Cloud-Failure-and-QoS-Simulation-main
plugins: anyio-4.15.1, asyncio-1.4.0
collected 122 items

tests/test_analytics.py ............................................... [  2%] (3 passed)
tests/test_e2e_integration_scenarios.py ............................... [  8%] (7 passed)
tests/test_explainability.py .......................................... [ 12%] (5 passed)
tests/test_failure_simulator.py ....................................... [ 17%] (6 passed)
tests/test_hysteresis.py .............................................. [ 29%] (14 passed)
tests/test_manual_override.py ......................................... [ 45%] (19 passed)
tests/test_monitoring_engine.py ....................................... [ 60%] (19 passed)
tests/test_qos_evaluator.py ........................................... [ 63%] (7 passed)
tests/test_recommendation_engine.py ................................... [ 68%] (6 passed)
tests/test_reliability_edge_cases.py .................................. [ 78%] (13 passed)
tests/test_sla_eligibility.py ......................................... [ 87%] (11 passed)
tests/test_ui_dashboard.py ............................................ [100%] (12 passed)

============================ 122 passed in 29.32s =============================
```

| Metric | Result |
| :--- | :--- |
| **Total Test Modules** | 12 modules |
| **Total Test Cases Executed** | **122** |
| **Total Passed** | **122 (100.0%)** |
| **Total Failed** | **0 (0.0%)** |
| **Total Skipped / XFailed** | **0 (0.0%)** |
| **Execution Duration** | **29.32 seconds** |

---

## 3. Module-by-Module Test Breakdown

### 3.1 `tests/test_analytics.py` (3 Tests)
Verifies service health classification and Plotly visualization builders:
1. `test_classify_service_health`: Confirms correct assignment of Healthy (green), Degraded (amber), and Down (red) based on baseline ratios and operational status.
2. `test_history_tracker`: Verifies snapshot persistence, metric recording across simulation sequence steps, and service history DataFrame conversion.
3. `test_chart_builders`: Validates that Plotly bar charts, radar charts, and timeline charts generate valid figures without runtime exceptions.

### 3.2 `tests/test_e2e_integration_scenarios.py` (7 Tests)
End-to-end integration scenarios simulating realistic operational lifecycles:
1. `test_scenario_a_normal_operation`: Clean baseline startup, SLA compliance, and deterministic winner selection (`SVC-C01`).
2. `test_scenario_b_performance_degradation`: Latency degradation triggers justified reselection to `SVC-C02` with complete explanation.
3. `test_scenario_c_sla_violation`: Hard SLA violation excludes active provider; emergency reselection succeeds.
4. `test_scenario_d_complete_outage`: Outage on active service immediately fails over to best eligible alternative.
5. `test_scenario_e_no_eligible_service`: All candidates in category offline or violating SLA; handles empty state cleanly.
6. `test_scenario_f_service_recovery`: Single restoration returns service to eligible pool; global reset re-anchors to baseline.
7. `test_scenario_g_manual_override_lifecycle`: Full override lifecycle: activation, locking, outage revocation, and manual return to automatic.

### 3.3 `tests/test_explainability.py` (5 Tests)
Verifies decision transparency and mathematical score breakdown:
1. `test_compare_service_metrics`: Validates raw metric differential calculation between two services.
2. `test_generate_detailed_reselection_explanation`: Checks structured markdown explanation including winner, runner-up, score deltas, and SLA exclusion reasons.
3. `test_candidate_comparison_table`: Confirms styling and ranking in candidate comparison DataFrame.
4. `test_build_three_way_comparison_dataframe`: Verifies 3-way comparison table across Selected, Previous, and Runner-up.
5. `test_reselection_audit_trail`: Verifies append-only chronological recording of all recommendation decisions.

### 3.4 `tests/test_failure_simulator.py` (6 Tests)
Verifies fault injection, recovery, and baseline immutability:
1. `test_latency_spike`: Validates positive latency additions and baseline preservation.
2. `test_simulate_outage`: Validates operational status transition to `UNAVAILABLE`.
3. `test_reduce_availability_and_bounds`: Checks availability percentage degradation and clamping at 0.0%.
4. `test_restore_service_idempotence`: Confirms single-service restoration returns exact baseline values across repeated calls.
5. `test_reset_simulation_idempotence`: Confirms global reset restores all 7 services across Compute and Storage.
6. `test_repeated_actions_do_not_accumulate_drift`: Proves zero baseline drift after 50 repeated cycles of fault injection and restoration.

### 3.5 `tests/test_hysteresis.py` (14 Tests)
Verifies switching stability, threshold margins, and cooldown logic:
1. `test_initial_selection_chooses_highest_scoring_service`: Rule A initial selection.
2. `test_current_service_retained_when_improvement_below_threshold`: Damping when improvement $< 5\%$.
3. `test_switching_occurs_when_improvement_exceeds_threshold`: Switching when improvement $\ge 5\%$.
4. `test_equal_qos_scores_do_not_cause_unnecessary_switching`: Tie stability.
5. `test_flapping_prevention_under_small_score_fluctuations`: Verifies zero switches under micro-jitter.
6. `test_current_service_outage_triggers_immediate_emergency_reselection`: Rule C outage bypass.
7. `test_current_service_sla_violation_triggers_immediate_emergency_reselection`: Rule D SLA breach bypass.
8. `test_cooldown_blocks_normal_performance_switching_when_active`: Cooldown enforcement.
9. `test_cooldown_never_blocks_emergency_reselection`: Emergency bypass of active cooldown.
10. `test_no_eligible_candidate_returns_correct_no_service_state`: Rule E empty candidate pool.
11. `test_recovered_services_reconsidered_correctly`: Rule F recovery consideration.
12. `test_recovery_does_not_cause_automatic_bounceback_without_satisfying_threshold`: Anti-bounceback.
13. `test_repeated_evaluations_with_unchanged_state_do_not_generate_duplicate_switching`: Idempotency.
14. `test_candidate_ranking_and_deterministic_tie_breaking_remain_unchanged`: Deterministic ranking.

### 3.6 `tests/test_manual_override.py` (19 Tests)
Verifies operator override permissions, request validation, and emergency revocation:
- Tests 01–04: Mode transitions, valid override activation, rejection of unknown and cross-category services.
- Tests 05–08: Rejection of unavailable and SLA-violating candidates; proof that manual override never bypasses hard SLA limits.
- Tests 09–12: Emergency revocation when overridden service suffers outage or SLA breach; failover to automatic mode.
- Tests 13–19: Audit trail event verification, timestamp logging, clear override idempotence, and session state consistency.

### 3.7 `tests/test_monitoring_engine.py` (19 Tests)
Verifies periodic background surveillance, health state machine, and deduplicated logging:
- Tests 01–05: Monitoring initialization, interval configuration, start, pause, resume, and reset.
- Tests 06–10: 4-tier health classification (`HEALTHY`, `DEGRADED`, `CRITICAL`, `DOWN`).
- Tests 11–15: Cycle execution, cycle counter increments, automatic reselection triggers upon health degradation.
- Tests 16–19: Event deduplication across identical cycles, thread-safety under multi-threaded execution, and error handling.

### 3.8 `tests/test_qos_evaluator.py` (7 Tests)
Verifies mathematical utility normalization, zero-division guards, and weight normalization:
- Lower-is-better normalization formula ($1.0$ at min, $0.0$ at max).
- Higher-is-better normalization formula ($1.0$ at max, $0.0$ at min).
- Out-of-bounds clamping to $[0.0, 1.0]$.
- Zero-division guard returning $1.0$ when $\max = \min$.
- Weight normalization summing to $1.0$.
- Weighted utility calculation sensitivity across all 4 metrics.

### 3.9 `tests/test_recommendation_engine.py` (6 Tests)
Verifies core recommendation orchestration:
- Deterministic candidate ranking and tie-breaking by `service_id`.
- Exclusion of `UNAVAILABLE` candidates.
- Latency spike triggering reselection.
- Category filtering (`Compute` vs `Storage`).
- Equal metric candidate tie-breaking.
- Empty candidate state handling.

### 3.10 `tests/test_reliability_edge_cases.py` (13 Boundary Edge Cases)
Verifies fault-tolerance and robustness under extreme edge conditions:
1. `test_edge_01_missing_qos_values`: Missing (`None`) QoS attributes handled safely without raising exceptions.
2. `test_edge_02_nan_and_infinite_values`: `math.nan` and `math.inf` rejected safely by SLA validator.
3. `test_edge_03_invalid_sla_configurations`: Negative latency and invalid percentage thresholds rejected by `__post_init__`.
4. `test_edge_04_equal_qos_scores_deterministic_tie_breaking`: Strict tie-breaking by alphabetical `service_id`.
5. `test_edge_05_empty_service_categories`: Non-existent or empty categories return clean empty recommendation.
6. `test_edge_06_all_services_unavailable`: Catastrophic outage returns `NO_SLA_COMPLIANT_SERVICE`.
7. `test_edge_07_all_services_sla_ineligible`: All services breaching SLA returns clean empty state.
8. `test_edge_08_repeated_monitoring_cycles_zero_drift`: 100 consecutive monitoring cycles cause 0 metric drift.
9. `test_edge_09_duplicate_audit_events_prevention`: 50 unchanged cycles generate 0 duplicate health events.
10. `test_edge_10_rapid_metric_fluctuations`: High-frequency metric jitter handled deterministically without state corruption.
11. `test_edge_11_repeated_service_restoration_idempotence`: 50 sequential restorations cause zero memory leaks or score shifts.
12. `test_edge_12_session_state_consistency_and_rerun_safety`: Simulates Streamlit rerun loop, verifying state consistency.
13. `test_edge_13_monitoring_exceptions_handled_safely`: Unhandled recommendation exception caught cleanly; logs `MONITORING_ERROR` without crashing.

### 3.11 `tests/test_sla_eligibility.py` (11 Tests)
Verifies strict SLA constraint filtering:
- Disqualification when Latency $>$ Max Latency threshold.
- Disqualification when Availability $<$ Min Availability threshold.
- Disqualification when Reliability $<$ Min Reliability threshold.
- Simultaneous multi-constraint breach reporting.
- Proof that highest-scoring candidate is rejected if it breaches SLA.
- Selection of highest-scoring *eligible* candidate.
- Restoration of SLA compliance restores eligibility.

### 3.12 `tests/test_ui_dashboard.py` (12 Tests — Headless Streamlit `AppTest`)
Automated UI interaction testing executing the actual `app.py` script headless:
1. `test_ui_01_dashboard_starts_and_renders_without_exceptions`: Initial render verification.
2. `test_ui_02_automatic_mode_active_by_default_and_selects_best_service`: Confirms automatic mode and initial winner.
3. `test_ui_03_manual_override_can_be_activated_for_eligible_service`: Activates manual override via UI button.
4. `test_ui_04_manual_override_selection_reflected_in_ui_and_audit_trail`: Confirms manual banner and audit table.
5. `test_ui_05_unavailable_service_cannot_be_selected_manually`: Rejects manual selection of offline candidate.
6. `test_ui_06_sla_violating_service_cannot_be_selected_manually`: Rejects manual selection of SLA-breaching candidate.
7. `test_ui_07_clearing_manual_override_returns_to_automatic_mode`: Reverts to automatic mode via UI button.
8. `test_ui_08_outage_during_manual_mode_triggers_emergency_failover`: UI verifies emergency revocation on outage.
9. `test_ui_09_no_eligible_service_state_handled_cleanly`: UI displays prominent alert banner when all candidates down.
10. `test_ui_10_monitoring_status_and_inspect_now_execution`: Clicks "Inspect Now" and checks cycle increment.
11. `test_ui_11_dashboard_behaves_consistently_across_failure_restore_and_reset`: Fault injection, restore, reset.
12. `test_ui_12_sla_breach_during_manual_mode_triggers_emergency_termination`: UI verifies emergency revocation on SLA breach.
