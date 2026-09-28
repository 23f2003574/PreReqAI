"""Integration tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade.

Reuses the reconciliation test module's own fixtures (_Recon and friends)
instead of re-deriving the same multi-service wiring a second time -- the
facade adds no business rules of its own, so these tests only need to
prove it calls the existing services in the right order and reports
their own outputs unchanged, not re-verify what those services already
have their own test coverage for.
"""

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_RECONCILIATION_NO_OP,
    IMPACT_RECONCILIATION_REPLACED,
    INTEGRITY_INVALID,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
)

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)


def _facade(recon):
    supersession_validation = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=supersession_validation,
        lifecycle_service=recon.lifecycle,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
        reconciliation_service=recon.service,
    ), supersession_validation


def test_evaluate_rejects_a_blank_task_id():
    recon = _Recon()
    facade, _ = _facade(recon)

    for bad in ("", None, 123):
        try:
            facade.evaluate(bad)
        except InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError:
            continue
        raise AssertionError("expected InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError")


def test_evaluate_clean_current_task_runs_the_lifecycle_and_persists_no_replacement_work():
    """A single-decision task (nothing to compare against) is CLEAN --
    the lifecycle records it once; there's nothing for reconciliation to
    have replaced."""
    recon = _Recon(resolution_chain=("d1",))
    facade, supersession = _facade(recon)

    result = facade.evaluate(TASK_ID)

    assert result.task_id == TASK_ID
    assert result.reconciliation_state is None
    assert result.reconciliation_operation_id is None
    assert result.decision_lineage_status == supersession.validate(TASK_ID).status
    record = recon.results.latest(TASK_ID)
    assert result.lifecycle_result_id == record.result_id
    assert result.authoritative_decision_id == record.authoritative_decision_id
    assert result.affected_artifacts == record.affected_artifacts
    assert result.final_verification_status == recon.verifier.verify(TASK_ID, record.result_id).status


def test_evaluate_changed_decision_reports_stale_artifacts_and_succeeds_end_to_end():
    """The default fixture's d1 -> d2 transition changes authorization_id/
    preflight_id/recovery_plan -- a real, non-trivial impact with
    affected artifacts, remediated end to end; whatever the underlying
    services still consider blocking is reported verbatim, unchanged."""
    recon = _Recon()
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    assert result.authoritative_decision_id == "d2"
    assert result.affected_artifacts
    assert result.remediation_operation_id is not None
    record = recon.results.latest(TASK_ID)
    verification = recon.verifier.verify(TASK_ID, record.result_id)
    assert result.blockers == tuple(record.blocking_artifacts) + tuple(verification.remaining_blockers)
    assert result.final_verification_status == verification.status


def test_evaluate_reports_unresolved_blockers_when_a_remediation_action_fails():
    recon = _Recon(fail=("invalidate",))
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    record = recon.results.latest(TASK_ID)
    assert result.blockers == tuple(record.blocking_artifacts) + tuple(
        recon.verifier.verify(TASK_ID, record.result_id).remaining_blockers
    )
    assert result.blockers != ()


def test_evaluate_reports_a_failed_final_verification():
    recon = _Recon(integrity=INTEGRITY_INVALID)
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    expected = recon.verifier.verify(TASK_ID, result.lifecycle_result_id)
    assert result.final_verification_status == expected.status
    assert expected.mismatches or expected.missing_evidence


def test_evaluate_second_call_reconciles_instead_of_re_running_the_lifecycle():
    """Idempotency: a second evaluate() for an unchanged task must go
    through reconciliation (NO_OP), never a second lifecycle run."""
    recon = _Recon()
    facade, _ = _facade(recon)

    first = facade.evaluate(TASK_ID)
    assert first.reconciliation_state is None
    history_after_first = recon.results.history(TASK_ID)
    assert len(history_after_first) == 1

    second = facade.evaluate(TASK_ID)

    assert second.reconciliation_state == IMPACT_RECONCILIATION_NO_OP
    assert second.lifecycle_result_id == first.lifecycle_result_id
    assert recon.results.history(TASK_ID) == history_after_first


def test_evaluate_second_call_detects_a_newly_stale_decision_via_reconciliation():
    """A decision added after the first evaluate() makes the persisted
    lifecycle result stale -- reconciliation must report REPLACED, and
    the facade must report the replacement's own operation id."""
    recon = _Recon()
    facade, _ = _facade(recon)

    facade.evaluate(TASK_ID)
    recon.add_decision("d3", minutes=30, authorization_id="auth-3", preflight_id="pre-3", recovery_plan="plan-c")
    recon.f.pointer.current_decision_id = "d3"

    second = facade.evaluate(TASK_ID)

    assert second.reconciliation_state == IMPACT_RECONCILIATION_REPLACED
    assert second.authoritative_decision_id == "d3"
    assert second.reconciliation_operation_id is not None
