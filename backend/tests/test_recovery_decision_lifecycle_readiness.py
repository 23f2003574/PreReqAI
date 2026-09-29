"""Tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService --
the final deploy/readiness gate composing #12's configuration validator,
#6/#7's health/dependency diagnostics, and the existing
lifecycle_result_service. No new checks are computed here: every
assertion traces back to an already-covered #6/#7/#12 diagnostic.
"""

from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    HEALTH_UNAVAILABLE,
    INTEGRITY_INVALID,
    LINEAGE_INVALID,
    LINEAGE_NOT_APPLICABLE,
    LINEAGE_VALID,
    READINESS_BLOCKED,
    READINESS_VERIFICATION_INVALID,
    READINESS_VERIFICATION_NOT_APPLICABLE,
    READINESS_VERIFICATION_VALID,
    READY,
    SUPERSESSION_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
)

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)


def _fake_supersession(status=SUPERSESSION_VALID):
    return SimpleNamespace(
        validate=lambda task_id: SimpleNamespace(status=status, issues=(), chain=(), terminal_decision_id=None),
    )


def _build(recon, supersession_validation_service=None, **overrides):
    supersession = supersession_validation_service or _fake_supersession()
    fields = dict(
        decision_store=recon.f.decision_store, resolution_service=recon.resolution,
        supersession_validation_service=supersession, impact_service=recon.f.impact,
        staleness_service=recon.f.staleness, lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier, lifecycle_service=recon.lifecycle,
        reconciliation_service=recon.service,
    )
    fields.update(overrides)
    configuration_validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**fields)
    health_fields = {k: v for k, v in fields.items() if k not in ("lifecycle_service", "reconciliation_service")}
    health_service = LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(
        configuration_validator=configuration_validator, **health_fields
    )
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService(
        configuration_validator=configuration_validator, health_service=health_service,
        lifecycle_result_service=recon.results,
    ), configuration_validator, health_service


def test_readiness_rejects_a_blank_but_given_task_id():
    recon = _Recon(resolution_chain=("d1",))
    service, _, _ = _build(recon)

    for bad in ("", 123):
        try:
            service.check(bad)
        except InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError:
            continue
        raise AssertionError("expected InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError")


def test_fully_ready_environment_with_no_task_given():
    recon = _Recon(resolution_chain=("d1",))
    service, _, _ = _build(recon)

    result = service.check()

    assert result.status == READY
    assert result.ready is True
    assert result.configuration_status == "valid"
    assert result.dependency_status == "healthy"
    assert result.decision_lineage_status == LINEAGE_NOT_APPLICABLE
    assert result.verification_status == READINESS_VERIFICATION_NOT_APPLICABLE
    assert result.blocking_conditions == ()
    assert result.issues == ()


def test_fully_ready_environment_with_a_clean_verified_task():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service, _, _ = _build(recon)

    result = service.check(TASK_ID)

    assert result.status == READY
    assert result.decision_lineage_status == LINEAGE_VALID
    assert result.verification_status == READINESS_VERIFICATION_VALID
    assert result.blocking_conditions == ()


def test_invalid_configuration_prevents_ready():
    recon = _Recon(resolution_chain=("d1",))
    service, _, _ = _build(recon, staleness_service=None)

    result = service.check()

    assert result.status == READINESS_BLOCKED
    assert result.configuration_status == "invalid"
    assert any("staleness_service" in issue for issue in result.issues)


def test_unavailable_dependency_prevents_ready():
    recon = _Recon(resolution_chain=("d1",))
    broken_results = SimpleNamespace(latest=lambda task_id: (_ for _ in ()).throw(RuntimeError("store down")))
    service, _, _ = _build(recon, lifecycle_result_service=broken_results)

    result = service.check(TASK_ID)

    assert result.status == READINESS_BLOCKED
    assert result.dependency_status == HEALTH_UNAVAILABLE


def test_invalid_decision_lineage_prevents_ready():
    """Real supersession validation (no recorded links for this fixture)
    reports the lineage invalid."""
    recon = _Recon()
    real_supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    service, _, _ = _build(recon, supersession_validation_service=real_supersession)

    result = service.check(TASK_ID)

    assert result.status == READINESS_BLOCKED
    assert result.decision_lineage_status == LINEAGE_INVALID
    assert any("decision lineage" in issue for issue in result.issues)


def test_task_level_blocker_prevents_ready():
    recon = _Recon(fail=("invalidate",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service, _, _ = _build(recon)

    result = service.check(TASK_ID)

    assert result.status == READINESS_BLOCKED
    assert result.blocking_conditions != ()
    assert any("blocking condition" in issue for issue in result.issues)


def test_failed_verification_prevents_ready():
    recon = _Recon(integrity=INTEGRITY_INVALID)
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service, _, _ = _build(recon)

    result = service.check(TASK_ID)

    assert result.status == READINESS_BLOCKED
    assert result.verification_status == READINESS_VERIFICATION_INVALID


def test_multiple_simultaneous_blockers_are_all_reported():
    recon = _Recon(fail=("invalidate",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    real_supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    service, _, _ = _build(recon, supersession_validation_service=real_supersession, staleness_service=None)

    result = service.check(TASK_ID)

    assert result.status == READINESS_BLOCKED
    assert result.configuration_status == "invalid"
    assert result.decision_lineage_status == LINEAGE_INVALID
    assert result.blocking_conditions != ()
    assert len(result.issues) >= 3


def test_readiness_never_mutates_persisted_state():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service, _, _ = _build(recon)
    history_before = recon.results.history(TASK_ID)

    service.check(TASK_ID)
    service.check(TASK_ID)
    service.check()

    assert recon.results.history(TASK_ID) == history_before


def test_repeated_checks_are_deterministic():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service, _, _ = _build(recon)

    first = service.check(TASK_ID)
    second = service.check(TASK_ID)

    assert first == second
