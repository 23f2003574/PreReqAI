"""Tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics
and its integration into #6's AgentTaskRecoveryExecutionDecisionLifecycleHealthResult.
"""

from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    DEPENDENCY_DECISION_STORE,
    DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE,
    DEPENDENCY_ORDER,
    DEPENDENCY_REMEDIATION_RECONCILIATION,
    DEPENDENCY_VERIFICATION,
    HEALTH_BLOCKED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    SUPERSESSION_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService,
)

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)


def _fake_supersession(status=SUPERSESSION_VALID):
    return SimpleNamespace(
        validate=lambda task_id: SimpleNamespace(status=status, issues=(), chain=(), terminal_decision_id=None),
    )


def _diagnostics(recon, **overrides):
    fields = dict(
        decision_store=recon.f.decision_store,
        resolution_service=recon.resolution,
        supersession_validation_service=_fake_supersession(),
        impact_service=recon.f.impact,
        staleness_service=recon.f.staleness,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
    )
    fields.update(overrides)
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics(**fields)


def _by_name(entries):
    return {entry.dependency: entry for entry in entries}


def test_diagnose_rejects_a_blank_task_id():
    recon = _Recon(resolution_chain=("d1",))
    diagnostics = _diagnostics(recon)

    for bad in ("", None, 123):
        try:
            diagnostics.diagnose(bad)
        except InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError:
            continue
        raise AssertionError("expected InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError")


def test_all_dependencies_healthy_after_a_clean_verified_evaluation():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    diagnostics = _diagnostics(recon)

    entries = diagnostics.diagnose(TASK_ID)

    assert len(entries) == 7
    assert [entry.dependency for entry in entries] == list(DEPENDENCY_ORDER)
    assert all(entry.status == HEALTH_HEALTHY for entry in entries)
    assert all(entry.blocking is False for entry in entries)
    assert all(entry.failure_reason is None for entry in entries)


def test_one_dependency_unavailable_is_isolated_from_the_rest():
    """A broken lifecycle result store must show up as unavailable only
    on the dependencies that actually read it (persistence, remediation/
    reconciliation, verification) -- decision store, resolver, impact and
    staleness are untouched by it and stay healthy."""
    recon = _Recon(resolution_chain=("d1",))
    broken_results = SimpleNamespace(latest=lambda task_id: (_ for _ in ()).throw(RuntimeError("store down")))
    diagnostics = _diagnostics(recon, lifecycle_result_service=broken_results)

    by_name = _by_name(diagnostics.diagnose(TASK_ID))

    assert by_name[DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE].status == HEALTH_UNAVAILABLE
    assert by_name[DEPENDENCY_REMEDIATION_RECONCILIATION].status == HEALTH_UNAVAILABLE
    assert by_name[DEPENDENCY_VERIFICATION].status == HEALTH_UNAVAILABLE
    assert "store down" in by_name[DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE].failure_reason
    for name in ("decision_store", "supersession_resolver", "impact_analyzer", "staleness_detector"):
        assert by_name[name].status == HEALTH_HEALTHY


def test_multiple_failures_are_each_reported_independently():
    recon = _Recon(resolution_chain=())  # no chain -> resolver blocked
    broken_store = SimpleNamespace(history=lambda task_id: (_ for _ in ()).throw(RuntimeError("disk full")))
    diagnostics = _diagnostics(recon, decision_store=broken_store)

    by_name = _by_name(diagnostics.diagnose(TASK_ID))

    assert by_name[DEPENDENCY_DECISION_STORE].status == HEALTH_UNAVAILABLE
    assert by_name["supersession_resolver"].status == HEALTH_BLOCKED
    failing = [entry for entry in by_name.values() if entry.status != HEALTH_HEALTHY]
    assert len(failing) >= 2


def test_task_level_blocker_is_distinguished_from_infrastructure_failure():
    recon = _Recon(fail=("invalidate",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    diagnostics = _diagnostics(recon)

    by_name = _by_name(diagnostics.diagnose(TASK_ID))

    blocker = by_name[DEPENDENCY_REMEDIATION_RECONCILIATION]
    assert blocker.status == HEALTH_BLOCKED
    assert blocker.blocking is True
    assert "blocking artifact" in blocker.failure_reason
    for name in ("decision_store", "supersession_resolver", "lifecycle_result_persistence", "verification"):
        assert by_name[name].status != HEALTH_UNAVAILABLE


def test_repeated_diagnostics_are_deterministic():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    diagnostics = _diagnostics(recon)

    first = diagnostics.diagnose(TASK_ID)
    second = diagnostics.diagnose(TASK_ID)

    assert first == second
    assert [entry.dependency for entry in first] == list(DEPENDENCY_ORDER)


def test_diagnose_never_mutates_persisted_state():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    diagnostics = _diagnostics(recon)
    history_before = recon.results.history(TASK_ID)

    diagnostics.diagnose(TASK_ID)
    diagnostics.diagnose(TASK_ID)

    assert recon.results.history(TASK_ID) == history_before


def test_health_result_from_6_carries_the_dependency_diagnostics():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service = LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(
        decision_store=recon.f.decision_store,
        resolution_service=recon.resolution,
        supersession_validation_service=_fake_supersession(),
        impact_service=recon.f.impact,
        staleness_service=recon.f.staleness,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
    )

    result = service.check(TASK_ID)

    assert len(result.dependency_diagnostics) == 7
    assert [entry.dependency for entry in result.dependency_diagnostics] == list(DEPENDENCY_ORDER)
    serialized = result.to_dict()["dependency_diagnostics"]
    assert len(serialized) == 7
    assert serialized[0]["dependency"] == DEPENDENCY_DECISION_STORE
