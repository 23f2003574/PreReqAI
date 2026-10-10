"""Tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService.

Reuses the reconciliation test module's own fixtures (_Recon and
friends), the same fixture-reuse convention every test file in this
package's own commit series already follows. Where the real
LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService would
report "invalid" for every fixture here (these fixtures record decisions
directly, never through the real supersession-linking service), a fake
supersession_validation_service stands in -- the same "fake the one
collaborator this fixture doesn't wire for real, keep everything else
real" approach _Recon itself already uses for resolution_service. The
one exception is the invalid-lineage test, which uses the real service
specifically because it naturally reports invalid here.
"""

from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CHECK_TASK_EXISTENCE,
    CHECK_UNRESOLVED_BLOCKERS,
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    SUPERSESSION_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService,
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


def _health(recon, supersession_validation_service=None, **overrides):
    fields = dict(
        decision_store=recon.f.decision_store,
        resolution_service=recon.resolution,
        supersession_validation_service=supersession_validation_service or _fake_supersession(),
        impact_service=recon.f.impact,
        staleness_service=recon.f.staleness,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
    )
    fields.update(overrides)
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(**fields)


def test_check_rejects_a_blank_task_id():
    recon = _Recon(resolution_chain=("d1",))
    service = _health(recon)

    for bad in ("", None, 123):
        try:
            service.check(bad)
        except InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError:
            continue
        raise AssertionError("expected InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError")


def test_healthy_state_after_a_clean_verified_evaluation():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service = _health(recon)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_HEALTHY
    assert result.issues == ()
    assert result.authoritative_decision_id == "d1"
    assert result.latest_lifecycle_result_id == recon.results.latest(TASK_ID).result_id
    assert all(check.passed for check in result.checks)


def test_task_blocker_is_reported_as_blocked_with_the_real_blocking_count():
    recon = _Recon(fail=("invalidate",))
    record = recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service = _health(recon)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_BLOCKED
    assert "unresolved blockers exist on the latest persisted lifecycle result" in result.issues
    blockers_check = [c for c in result.checks if c.name == CHECK_UNRESOLVED_BLOCKERS][0]
    assert blockers_check.passed is False
    assert str(len(record.blocking_artifacts)) in blockers_check.detail


def test_stale_lifecycle_result_is_degraded_not_blocked():
    """A cleanly persisted result with nothing blocking, whose
    authoritative decision has since moved on -- verification catches it
    as stale even though nothing about the old record itself is
    blocking."""
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    recon.add_decision("d2", minutes=5, authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b")
    recon.resolution.resolve = lambda task_id: SimpleNamespace(
        resolution_state="resolved", terminal_decision_id="d2", chain=tuple(recon.chain),
    )
    service = _health(recon)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_DEGRADED
    assert any("no longer verifies" in issue for issue in result.issues)


def test_invalid_lineage_is_blocked_using_the_real_supersession_validation_service():
    recon = _Recon()
    real_supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    service = _health(recon, supersession_validation_service=real_supersession)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_BLOCKED
    assert any("supersession chain invalid" in issue for issue in result.issues)


def test_missing_persistence_is_degraded_with_no_authoritative_decision_lost():
    recon = _Recon(resolution_chain=("d1",))
    service = _health(recon)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_DEGRADED
    assert result.latest_lifecycle_result_id is None
    assert result.authoritative_decision_id == "d1"
    assert "no persisted lifecycle result found for task_id" in result.issues


def test_dependency_failure_is_unavailable_not_blocked():
    """An exception from a composed service (store down, dependency
    misconfigured) must be distinguishable from a legitimate task-level
    blocker."""
    recon = _Recon(resolution_chain=("d1",))
    broken_results = SimpleNamespace(latest=lambda task_id: (_ for _ in ()).throw(RuntimeError("store down")))
    service = _health(recon, lifecycle_result_service=broken_results)

    result = service.check(TASK_ID)

    assert result.status == HEALTH_UNAVAILABLE
    assert any("unavailable" in issue for issue in result.issues)


def test_missing_task_is_blocked_and_fails_closed():
    recon = _Recon(resolution_chain=())
    service = _health(recon)

    result = service.check("never-seen-task")

    assert result.status == HEALTH_BLOCKED
    assert "no decisions recorded for task_id" in result.issues
    existence_check = [c for c in result.checks if c.name == CHECK_TASK_EXISTENCE][0]
    assert existence_check.passed is False


def test_repeated_checks_are_deterministic():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service = _health(recon)

    first = service.check(TASK_ID)
    second = service.check(TASK_ID)

    assert first.status == second.status
    assert first.checks == second.checks
    assert first.issues == second.issues
    assert first.authoritative_decision_id == second.authoritative_decision_id
    assert first.latest_lifecycle_result_id == second.latest_lifecycle_result_id


def test_check_never_mutates_persisted_state():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    service = _health(recon)
    history_before = recon.results.history(TASK_ID)

    service.check(TASK_ID)
    service.check(TASK_ID)

    assert recon.results.history(TASK_ID) == history_before
