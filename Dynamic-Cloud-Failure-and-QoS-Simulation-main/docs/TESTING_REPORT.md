# Automated Testing & Verification Report

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Quality Assurance & Test Suite Execution Report  
**Test Suite Framework:** Pytest 9.2.0 with `streamlit.testing.v1.AppTest`  
**Execution Timestamp:** November 20, 2026  
**Final Verdict:** **138 of 138 PASSED (100.0% Pass Rate, 0 Failures, 0 Skipped)**  

---

## 1. Test Environment Specification

The test suite was executed in an isolated local Python virtual environment:
- **Operating System:** Microsoft Windows 11 Enterprise (64-bit)
- **Python Version:** 3.11.9 (64-bit AMD64)
- **Pytest Version:** pytest 9.2.0 (pluggy 1.7.0)
- **Test Runner Command:** `python -m pytest tests -v`
- **Execution Wall-Clock Time:** `20.07 seconds`

---

## 2. Test Execution Summary

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\gost\Desktop\simplified-project\Dynamic-Cloud-Failure-and-QoS-Simulation-main
plugins: anyio-4.16.0
collected 138 items

tests/test_analytics.py ............................................... [  2%] (4 passed)
tests/test_e2e_integration_scenarios.py ............................... [  7%] (7 passed)
tests/test_explainability.py .......................................... [ 11%] (5 passed)
tests/test_failure_simulator.py ....................................... [ 15%] (6 passed)
tests/test_hysteresis.py .............................................. [ 26%] (15 passed)
tests/test_manual_override.py ......................................... [ 37%] (15 passed)
tests/test_monitoring.py .............................................. [ 49%] (17 passed)
tests/test_persistence.py ............................................ [ 60%] (15 passed)
tests/test_qos_evaluator.py ........................................... [ 67%] (9 passed)
tests/test_recommendation_engine.py ................................... [ 71%] (6 passed)
tests/test_reliability_edge_cases.py .................................. [ 81%] (13 passed)
tests/test_sla_eligibility.py ......................................... [ 91%] (14 passed)
tests/test_ui_dashboard.py ............................................ [100%] (12 passed)

============================ 138 passed in 20.07s =============================
```

| Metric | Result |
| :--- | :--- |
| **Total Test Modules** | 13 test modules |
| **Total Test Cases Executed** | **138** |
| **Total Passed** | **138 (100.0%)** |
| **Total Failed** | **0 (0.0%)** |
| **Total Skipped / XFailed** | **0 (0.0%)** |
| **Execution Duration** | **20.07 seconds** |

---

## 3. Module-by-Module Test Breakdown

### 3.1 `tests/test_analytics.py` (4 Tests)
Verifies service health classification and Plotly visualization builders:
1. `test_classify_service_health`: Confirms correct assignment of Healthy (green), Degraded (amber), and Down (red) based on baseline ratios and operational status.
2. `test_history_tracker`: Verifies snapshot persistence, metric recording across simulation sequence steps, and service history DataFrame conversion.
3. `test_chart_builders`: Validates that Plotly bar charts, radar charts, and timeline charts generate valid figures without runtime exceptions.
4. `test_enhanced_charts_respond_to_failure_simulation_and_reselection`: Verifies that charts dynamically re-render upon simulated faults and reselection transitions.

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

### 3.5 `tests/test_hysteresis.py` (15 Tests)
Verifies switching stability, threshold margins, and cooldown logic:
1. `test_initial_selection_chooses_highest_scoring_service`: Rule A initial selection.
2. `test_current_service_retained_when_improvement_below_threshold`: Damping when improvement $< 5\%$.
3. `test_switching_occurs_when_improvement_exceeds_threshold`: Switching when improvement $\ge 5\%$.
4. `test_equal_qos_scores_do_not_cause_unnecessary_switching`: Tie stability.
5. `test_flapping_prevention_under_small_score_fluctuations`: Verifies zero switches under micro-jitter.
6. `test_current_service_outage_triggers_immediate_emergency_reselection`: Rule C outage bypass.
7. `test_current_service_sla_violation_triggers_immediate_emergency_reselection`: Rule C SLA violation bypass.
8. `test_cooldown_blocks_normal_performance_switching_when_active`: Cooldown suppression of non-emergency switches.
9. `test_cooldown_never_blocks_emergency_reselection`: Emergency bypass of active cooldown timers.
10. `test_no_eligible_candidate_returns_correct_no_service_state`: Clean empty state when all candidates ineligible.
11. `test_recovered_services_reconsidered_correctly`: Recovered candidate evaluation.
12. `test_recovery_does_not_cause_automatic_bounceback_without_satisfying_threshold`: Hysteresis blocks bounceback without margin.
13. `test_repeated_evaluations_with_unchanged_state_do_not_generate_duplicate_switching`: Deterministic idempotence.
14. `test_existing_phase1_sla_tests_continue_to_pass_with_hysteresis`: Non-regression preservation.
15. `test_candidate_ranking_and_deterministic_tie_breaking_remain_unchanged`: Tie-breaking consistency.

### 3.6 `tests/test_manual_override.py` (15 Tests)
Verifies operator control, guardrail validation, and emergency termination:
1. `test_01_automatic_mode_selects_best_eligible_service`: Baseline automatic mode validation.
2. `test_02_manual_mode_selects_requested_eligible_service`: Manual activation for eligible candidate.
3. `test_03_unknown_service_id_is_rejected`: Rejection of invalid service identifier.
4. `test_04_cross_category_service_is_rejected`: Rejection of mismatched category service.
5. `test_05_unavailable_service_cannot_be_manually_selected`: Guardrail preventing selection of offline service.
6. `test_06_sla_violating_service_cannot_be_manually_selected`: Guardrail preventing selection of SLA-breaching service.
7. `test_07_clearing_override_restores_automatic_mode_cleanly`: Return to automatic mode restores highest-ranked candidate.
8. `test_08_manual_override_never_bypasses_sla_constraints_even_directly`: Direct invocation enforcement.
9. `test_09_emergency_outage_immediately_terminates_manual_override`: Outage triggers emergency revocation and failover.
10. `test_10_emergency_sla_violation_immediately_terminates_manual_override`: SLA breach triggers emergency revocation and failover.
11. `test_11_periodic_monitoring_continues_in_manual_mode`: Continuous health surveillance during manual mode.
12. `test_12_recovered_service_does_not_displace_valid_manual_override`: Stability of healthy manual override.
13. `test_13_hysteresis_still_works_in_automatic_mode`: Automatic mode behavior preserved.
14. `test_14_duplicate_override_and_monitoring_events_prevented`: Audit deduplication.
15. `test_15_full_integration_explainability_sla_hysteresis_monitoring_and_reset`: Full integration lifecycle.

### 3.7 `tests/test_monitoring.py` (17 Tests)
Verifies background surveillance, state transitions, and interval throttling:
1. `test_monitoring_engine_initialization`: Clean configuration setup.
2. `test_monitoring_engine_initialized_paused`: Safe initial paused state.
3. `test_monitoring_configuration_validation`: Rejection of non-positive intervals.
4. `test_periodic_monitoring_execution_respects_interval`: Interval throttling enforcement.
5. `test_service_health_classification_states`: Classification across HEALTHY, DEGRADED, UNAVAILABLE.
6. `test_detection_of_sla_violations`: Immediate breach detection and event emission.
7. `test_detection_of_unavailable_services`: Outage event logging.
8. `test_detection_of_service_recovery`: Transition back to HEALTHY/AVAILABLE.
9. `test_automatic_reselection_after_emergency_failure`: Surveillance-driven failover.
10. `test_no_eligible_service_state_and_recovery`: Graceful handling of category-wide outages.
11. `test_event_history_recording_and_deduplication`: Idempotent event logging without spam.
12. `test_sync_external_selection_updates_internal_state`: Synchronizing external selection state.
13. `test_reset_monitoring_engine`: Clean state reset.
14. `test_clear_events`: Audit history purge.
15. `test_inspect_now_triggers_cycle_regardless_of_interval`: On-demand manual inspection.
16. `test_monitoring_engine_thread_safety_concept`: Thread safety under concurrent invocations.
17. `test_get_summary_statistics`: Metric summary aggregation accuracy.

### 3.8 `tests/test_persistence.py` (15 Tests — Phase 9 Persistence & Audit Management)
Verifies SQLite storage, WAL mode, migrations, baseline preservation, and ACID compliance:
1. `test_01_database_initialization_and_pragmas`: Confirms WAL mode, foreign keys, busy timeout, and connection creation.
2. `test_02_schema_and_index_creation`: Confirms creation of all 7 relational tables and 12 performance indexes.
3. `test_03_migration_versioning_and_idempotence`: Confirms version tracking table and idempotent re-migration.
4. `test_04_service_state_persistence`: Verifies insert and retrieval of mutated QoS metrics and operational status.
5. `test_05_service_state_recovery_after_simulated_restart`: Confirms that restarting restores simulation state while strictly preserving immutable baseline bounds.
6. `test_06_failure_event_persistence`: Verifies recording and chronological retrieval of fault injection events.
7. `test_07_monitoring_event_persistence`: Confirms batch persistence and retrieval of periodic monitoring cycles.
8. `test_08_reselection_audit_persistence`: Verifies append-only storage of reselection decisions and explainability reasons.
9. `test_09_manual_override_history_persistence`: Verifies recording of override activations, rejections, and emergency revocations.
10. `test_10_transaction_rollback`: Confirms atomic rollback on write error, preserving database consistency.
11. `test_11_duplicate_event_handling`: Confirms upsert idempotency and deduplication across simulation cycles.
12. `test_12_reset_without_deleting_audit_history`: Proves simulation reset clears service mutations while strictly preserving historical audit records.
13. `test_13_concurrent_database_access`: Confirms multi-threaded reader/writer safety without SQLITE_BUSY deadlocks.
14. `test_14_invalid_persisted_data_handling`: Confirms graceful recovery and boundary clamping upon corrupted or missing records.
15. `test_15_database_recovery_and_error_handling`: Confirms resilience against malformed schema and missing database files.

### 3.9 `tests/test_qos_evaluator.py` (9 Tests)
Verifies normalization and multi-attribute utility formulas:
- Linear normalization for lower-is-better metrics (Latency, Cost).
- Linear normalization for higher-is-better metrics (Availability, Reliability).
- Equal min-max normalization guard handling ($U = 1.0$).
- Weight validation, non-negativity, and auto-sum normalization.
- Additive weighted sum aggregate calculation.
- Batch evaluation across all candidate services.
- Latency and cost inverse sensitivity.
- Availability and reliability positive sensitivity.
- Zero and negative weight edge-case handling.

### 3.10 `tests/test_recommendation_engine.py` (6 Tests)
Verifies core ranking pipeline:
- Deterministic winner selection.
- Exclusion of UNAVAILABLE candidates.
- Reselection triggered by latency spikes.
- Strict category filtering (Compute vs Storage).
- Deterministic tie-breaking on identical utility scores.
- Clean handling when zero eligible candidates exist.

### 3.11 `tests/test_reliability_edge_cases.py` (13 Boundary Edge Cases)
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

### 3.12 `tests/test_sla_eligibility.py` (14 Tests)
Verifies strict SLA constraint filtering:
- Disqualification when Latency $>$ Max Latency threshold.
- Disqualification when Availability $<$ Min Availability threshold.
- Disqualification when Reliability $<$ Min Reliability threshold.
- Simultaneous multi-constraint breach reporting.
- Proof that highest-scoring candidate is rejected if it breaches SLA.
- Selection of highest-scoring *eligible* candidate.
- Restoration of SLA compliance restores eligibility.
- Existing category filtering preserved.
- Deterministic tie-breaking preserved.
- QoS weights and normalization preserved.
- Invalid SLA configuration rejected safely.
- Missing, NaN, and infinite metrics handled safely.
- Total category breach returns clean empty state.
- Total category outage returns clean empty state.

### 3.13 `tests/test_ui_dashboard.py` (12 Tests — Headless Streamlit `AppTest`)
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
