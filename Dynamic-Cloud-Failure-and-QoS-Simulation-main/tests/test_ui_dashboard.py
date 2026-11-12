"""Automated Streamlit Dashboard UI Tests using streamlit.testing.v1.AppTest.

Verifies UI state consistency, operating mode transitions, SLA/availability
guardrails, emergency override termination, monitoring dashboard rendering,
and failure simulation feedback without real sleeps or external infrastructure.
"""

from pathlib import Path
from streamlit.testing.v1 import AppTest

from src.override_manager import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    OVERRIDE_EVENT_EMERGENCY_TERMINATED,
    OVERRIDE_EVENT_REJECTED,
)


APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _new_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert not at.exception, f"Unexpected app exception on launch: {at.exception}"
    return at


def _find_sidebar_button(at: AppTest, label_substring: str):
    return next(b for b in at.sidebar.button if label_substring in b.label)


def _find_sidebar_selectbox(at: AppTest, label_substring: str):
    return next(s for s in at.sidebar.selectbox if label_substring in s.label)


def _find_sidebar_number_input(at: AppTest, label_substring: str):
    return next(n for n in at.sidebar.number_input if label_substring in n.label)


def _metric_value_by_label(at: AppTest, label_substring: str) -> str:
    m = next(metric for metric in at.metric if label_substring in metric.label)
    return str(m.value)


def _select_sidebar_target_service(at: AppTest, service_id: str) -> None:
    target_sel = _find_sidebar_selectbox(at, "Target Service")
    # Select by exact service_id if present in options, otherwise substring match on formatted options
    matched = next(
        (opt for opt in target_sel.options if service_id == opt or service_id in opt),
        service_id,
    )
    target_sel.set_value(matched)


def _all_rendered_text(at: AppTest) -> str:
    chunks = []
    for elem_list in (
        at.markdown,
        at.info,
        at.success,
        at.warning,
        at.error,
        at.caption,
        at.header,
        at.subheader,
        at.title,
    ):
        for item in elem_list:
            val = getattr(item, "value", None)
            if val is not None:
                chunks.append(str(val))
    return "\n".join(chunks)


def test_ui_01_dashboard_starts_and_renders_without_exceptions():
    """Test UI 1: App renders cleanly with KPIs, monitoring bar, and operating mode panel."""
    at = _new_app()
    rendered = _all_rendered_text(at)
    assert "Operating Mode & Service Selection Control" in rendered
    assert "Periodic Service Monitoring Dashboard" in rendered
    assert _metric_value_by_label(at, "Selected Service") != ""


def test_ui_02_automatic_mode_active_by_default_and_selects_best_service():
    """Test UI 2: Launches in AUTOMATIC mode and selects highest-ranked eligible Compute service."""
    at = _new_app()
    mgr = at.session_state["override_manager"]
    assert mgr.mode == MODE_AUTOMATIC
    assert at.session_state["prev_recommended_id"] == "SVC-C01"
    assert _metric_value_by_label(at, "Selected Service") == "NovaCompute Standard"
    assert _metric_value_by_label(at, "Active Selected") == "SVC-C01"


def test_ui_03_manual_override_can_be_activated_for_eligible_service():
    """Test UI 3: Selecting an eligible service and clicking Activate enters MANUAL_OVERRIDE."""
    at = _new_app()

    sel = at.selectbox(key="manual_override_target_select")
    assert any("SVC-C02" in opt for opt in sel.options)
    sel.set_value("SVC-C02")

    reason_box = at.text_input(key="manual_override_reason_input")
    reason_box.set_value("UI automated override verification")

    at.button(key="btn_activate_manual_override").click().run()
    assert not at.exception

    mgr = at.session_state["override_manager"]
    assert mgr.mode == MODE_MANUAL
    assert mgr.requested_service_id == "SVC-C02"
    assert at.session_state["prev_recommended_id"] == "SVC-C02"


def test_ui_04_manual_override_selection_reflected_in_ui_and_audit_trail():
    """Test UI 4: Active manual override displays distinct UI status and updates audit trail."""
    at = _new_app()
    at.selectbox(key="manual_override_target_select").set_value("SVC-C02")
    at.button(key="btn_activate_manual_override").click().run()
    assert not at.exception

    rendered = _all_rendered_text(at)
    assert "MANUAL_OVERRIDE" in rendered
    assert "SVC-C02" in rendered
    audit_df = at.session_state["reselection_audit_trail"].to_dataframe()
    assert not audit_df.empty
    assert audit_df.iloc[-1]["Selected Service"] == "SVC-C02"
    assert audit_df.iloc[-1]["Operating Mode"] == MODE_MANUAL


def test_ui_05_unavailable_service_cannot_be_selected_manually():
    """Test UI 5: Outage service is excluded from override options and rejected on backend request."""
    at = _new_app()

    # Target SVC-C03 in sidebar and trigger outage
    _select_sidebar_target_service(at, "SVC-C03")
    _find_sidebar_button(at, "Simulate Outage").click().run()
    assert not at.exception

    # Unavailable service must not appear as an eligible manual override option
    ovr_sel = at.selectbox(key="manual_override_target_select")
    assert not any("SVC-C03" in opt for opt in ovr_sel.options)

    # Even if directly submitted via backend manager, it is strictly rejected
    mgr = at.session_state["override_manager"]
    sim = at.session_state["simulator"]
    sla = at.session_state["active_sla"]
    ok, msg, _ = mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C03", sla)
    assert ok is False
    assert "unavailable" in msg.lower()
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.event_history[-1].event_type == OVERRIDE_EVENT_REJECTED


def test_ui_06_sla_violating_service_cannot_be_selected_manually():
    """Test UI 6: SLA-violating service is excluded from manual selector & blocked by validator."""
    at = _new_app()

    # Spike latency on SVC-C02 well above SLA max latency (default 150ms)
    _select_sidebar_target_service(at, "SVC-C02")
    _find_sidebar_number_input(at, "Spike (ms)").set_value(500)
    _find_sidebar_button(at, "Inject Latency Spike").click().run()
    assert not at.exception

    ovr_sel = at.selectbox(key="manual_override_target_select")
    assert not any("SVC-C02" in opt for opt in ovr_sel.options)

    mgr = at.session_state["override_manager"]
    sim = at.session_state["simulator"]
    sla = at.session_state["active_sla"]
    ok, msg, _ = mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)
    assert ok is False
    assert "sla" in msg.lower()
    assert mgr.mode == MODE_AUTOMATIC


def test_ui_07_clearing_manual_override_returns_to_automatic_mode():
    """Test UI 7: Clicking Clear Override restores AUTOMATIC mode and #1 automatic service."""
    at = _new_app()

    at.selectbox(key="manual_override_target_select").set_value("SVC-C02")
    at.button(key="btn_activate_manual_override").click().run()
    assert at.session_state["override_manager"].mode == MODE_MANUAL
    assert at.session_state["prev_recommended_id"] == "SVC-C02"

    at.button(key="btn_clear_manual_override").click().run()
    assert not at.exception

    assert at.session_state["override_manager"].mode == MODE_AUTOMATIC
    assert at.session_state["prev_recommended_id"] == "SVC-C01"
    rendered = _all_rendered_text(at)
    assert "AUTOMATIC" in rendered


def test_ui_08_outage_during_manual_mode_triggers_emergency_failover():
    """Test UI 8: Outage on manually selected service immediately ends override and switches to fallback."""
    at = _new_app()

    # Activate manual override on SVC-C02
    at.selectbox(key="manual_override_target_select").set_value("SVC-C02")
    at.button(key="btn_activate_manual_override").click().run()
    assert at.session_state["override_manager"].mode == MODE_MANUAL
    assert at.session_state["prev_recommended_id"] == "SVC-C02"

    # Trigger outage on SVC-C02 via sidebar
    _select_sidebar_target_service(at, "SVC-C02")
    _find_sidebar_button(at, "Simulate Outage").click().run()
    assert not at.exception

    mgr = at.session_state["override_manager"]
    assert mgr.mode == MODE_AUTOMATIC
    assert at.session_state["prev_recommended_id"] == "SVC-C01"
    assert any(e.event_type == OVERRIDE_EVENT_EMERGENCY_TERMINATED for e in mgr.event_history)
    error_texts = "\n".join(str(e.value) for e in at.error)
    assert "terminated" in error_texts.lower() or "outage" in error_texts.lower()


def test_ui_09_no_eligible_service_state_handled_cleanly():
    """Test UI 9: Universal SLA tightening leaves 0 eligible services cleanly without crash."""
    at = _new_app()

    # Set impossibly tight Max Allowed Latency (ms) (e.g. 10ms < min 25ms) so zero Compute services comply
    sla_lat_input = _find_sidebar_number_input(at, "Max Allowed Latency")
    sla_lat_input.set_value(10.0).run()
    assert not at.exception

    assert at.session_state["prev_recommended_id"] is None
    assert at.button(key="btn_activate_manual_override").disabled is True
    rendered = _all_rendered_text(at)
    assert "No Eligible Service" in rendered or "No SLA-Compliant Service Available" in rendered


def test_ui_10_monitoring_status_and_inspect_now_execution():
    """Test UI 10: Periodic monitoring dashboard bar renders metrics and runs on demand."""
    at = _new_app()
    mon = at.session_state["monitoring_engine"]
    initial_cycles = mon.cycle_count

    at.button(key="btn_monitoring_inspect_now").click().run()
    assert not at.exception

    assert at.session_state["monitoring_engine"].cycle_count > initial_cycles
    assert _metric_value_by_label(at, "Monitored Services") == "5"
    assert _metric_value_by_label(at, "Active Selected") == "SVC-C01"


def test_ui_11_dashboard_behaves_consistently_across_failure_restore_and_reset():
    """Test UI 11: Latency spike -> Restore -> Reset lifecycle preserves valid UI & backend state."""
    at = _new_app()

    # Step 1: Spike latency on SVC-C01 -> reselection to SVC-C02
    _select_sidebar_target_service(at, "SVC-C01")
    _find_sidebar_number_input(at, "Spike (ms)").set_value(450)
    _find_sidebar_button(at, "Inject Latency Spike").click().run()
    assert not at.exception
    assert at.session_state["prev_recommended_id"] == "SVC-C02"

    # Step 2: Activate manual override on SVC-C03 while SVC-C01 is degraded
    at.selectbox(key="manual_override_target_select").set_value("SVC-C03")
    at.button(key="btn_activate_manual_override").click().run()
    assert not at.exception
    assert at.session_state["prev_recommended_id"] == "SVC-C03"

    # Step 3: Restore SVC-C01 -> recovered service must NOT displace valid manual override SVC-C03
    _select_sidebar_target_service(at, "SVC-C01")
    _find_sidebar_button(at, "Restore Service").click().run()
    assert not at.exception
    assert at.session_state["override_manager"].mode == MODE_MANUAL
    assert at.session_state["prev_recommended_id"] == "SVC-C03"

    # Step 4: Reset all services -> returns cleanly to AUTOMATIC and SVC-C01
    _find_sidebar_button(at, "Reset All Services").click().run()
    assert not at.exception
    assert at.session_state["override_manager"].mode == MODE_AUTOMATIC
    assert at.session_state["prev_recommended_id"] == "SVC-C01"


def test_ui_12_sla_breach_during_manual_mode_triggers_emergency_termination():
    """Test UI 12: Tightening SLA threshold while manual override breaches SLA terminates override."""
    at = _new_app()

    # Activate manual override on SVC-C03 (baseline latency 120ms)
    at.selectbox(key="manual_override_target_select").set_value("SVC-C03")
    at.button(key="btn_activate_manual_override").click().run()
    assert not at.exception
    assert at.session_state["override_manager"].mode == MODE_MANUAL
    assert at.session_state["prev_recommended_id"] == "SVC-C03"

    # Tighten Max Allowed Latency to 60ms -> SVC-C03 violates SLA, SVC-C01 (45ms) complies
    _find_sidebar_number_input(at, "Max Allowed Latency").set_value(60.0).run()
    assert not at.exception

    assert at.session_state["override_manager"].mode == MODE_AUTOMATIC
    assert at.session_state["prev_recommended_id"] == "SVC-C01"
    assert any(
        e.event_type == OVERRIDE_EVENT_EMERGENCY_TERMINATED
        for e in at.session_state["override_manager"].event_history
    )
