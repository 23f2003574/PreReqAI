"""Integration tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade
and the AgentTaskRecoveryExecutionDecisionLifecycleResult contract it returns.

Reuses the reconciliation test module's own fixtures (_Recon and friends)
instead of re-deriving the same multi-service wiring a second time -- the
facade adds no business rules of its own, so these tests only need to
prove it calls the existing services in the right order and reports
their own outputs, unchanged, through the stable contract -- not
re-verify what those services already have their own test coverage for.
"""

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleResult,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_UNSAFE,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    INTEGRITY_INVALID,
    LIFECYCLE_VERIFICATION_INVALID,
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


def _ground_truth(recon):
    """The same values a caller could only get by calling the underlying
    services directly and merging their results by hand -- used to prove
    the facade's contract reports them unchanged."""
    record = recon.results.latest(TASK_ID)
    return record, recon.verifier.verify(TASK_ID, record.result_id)


def test_evaluate_rejects_a_blank_task_id():
    recon = _Recon()
    facade, _ = _facade(recon)

    for bad in ("", None, 123):
        try:
            facade.evaluate(bad)
        except InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError:
            continue
        raise AssertionError("expected InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError")


def test_evaluate_returns_the_stable_lifecycle_result_contract():
    """The facade must return the public contract type, not any internal
    service's own result shape."""
    recon = _Recon()
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    assert isinstance(result, AgentTaskRecoveryExecutionDecisionLifecycleResult)
    assert result.to_dict()["task_id"] == TASK_ID


def test_evaluate_reports_a_successful_end_to_end_remediation():
    """The default fixture's d1 -> d2 transition is a real, non-trivial
    impact, remediated end to end; whatever the underlying services still
    consider blocking is reported verbatim, unchanged."""
    recon = _Recon()
    facade, supersession = _facade(recon)

    result = facade.evaluate(TASK_ID)

    record, verification = _ground_truth(recon)
    assert result.overall_status == IMPACT_LIFECYCLE_REMEDIATED
    assert result.authoritative_decision_id == "d2"
    assert result.affected_artifacts
    assert result.remediation_operation_id == record.operation_id
    assert result.decision_lineage_status == supersession.validate(TASK_ID).status
    assert result.blocking_conditions == tuple(record.blocking_artifacts) + tuple(verification.remaining_blockers)
    assert result.verification_status == verification.status
    assert result.diagnostics == (
        tuple(record.errors) + tuple(verification.mismatches) + tuple(verification.missing_evidence)
    )


def test_evaluate_reports_a_blocked_lifecycle_explicitly():
    recon = _Recon(fail=("invalidate",))
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    record, verification = _ground_truth(recon)
    assert result.overall_status == IMPACT_LIFECYCLE_BLOCKED
    assert result.blocking_conditions == tuple(record.blocking_artifacts) + tuple(verification.remaining_blockers)
    assert result.blocking_conditions != ()


def test_evaluate_reports_a_partially_completed_up_to_date_lifecycle():
    """Priming an audited operation for the same decision change before
    the facade's first evaluate() means that first run has nothing new to
    apply -- reported as the lifecycle's own UP_TO_DATE, not REMEDIATED,
    with no new operation id."""
    recon = _Recon()
    recon.lifecycle.run(TASK_ID)
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_UP_TO_DATE
    assert result.remediation_operation_id is None


def test_evaluate_reports_a_failed_unresolved_lifecycle():
    """No authoritative decision can be established -- fails closed as
    UNRESOLVED, with the underlying service's own error preserved in
    diagnostics verbatim."""
    recon = _Recon(resolution_chain=())
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    record, verification = _ground_truth(recon)
    assert result.overall_status == IMPACT_LIFECYCLE_UNRESOLVED
    assert result.authoritative_decision_id is None
    assert result.remediation_operation_id is None
    assert result.diagnostics == (
        tuple(record.errors) + tuple(verification.mismatches) + tuple(verification.missing_evidence)
    )
    assert result.diagnostics != ()


def test_evaluate_reports_a_failed_verification():
    recon = _Recon(integrity=INTEGRITY_INVALID)
    facade, _ = _facade(recon)

    result = facade.evaluate(TASK_ID)

    record, verification = _ground_truth(recon)
    assert result.overall_status == IMPACT_LIFECYCLE_UNSAFE
    assert result.verification_status == LIFECYCLE_VERIFICATION_INVALID
    assert verification.mismatches
    assert result.diagnostics == (
        tuple(record.errors) + tuple(verification.mismatches) + tuple(verification.missing_evidence)
    )


def test_evaluate_second_call_reconciles_instead_of_re_running_the_lifecycle():
    """Idempotency: a second evaluate() for an unchanged task must go
    through reconciliation (NO_OP), never a second lifecycle run."""
    recon = _Recon()
    facade, _ = _facade(recon)

    first = facade.evaluate(TASK_ID)
    history_after_first = recon.results.history(TASK_ID)
    assert len(history_after_first) == 1

    second = facade.evaluate(TASK_ID)

    assert second.overall_status == first.overall_status
    assert second.authoritative_decision_id == first.authoritative_decision_id
    assert recon.results.history(TASK_ID) == history_after_first


def test_evaluate_second_call_detects_a_newly_stale_decision_via_reconciliation():
    """A decision added after the first evaluate() makes the persisted
    lifecycle result stale -- reconciliation runs a fresh lifecycle as the
    replacement, and the facade reports that replacement's own operation
    id and authoritative decision."""
    recon = _Recon()
    facade, _ = _facade(recon)

    facade.evaluate(TASK_ID)
    recon.add_decision("d3", minutes=30, authorization_id="auth-3", preflight_id="pre-3", recovery_plan="plan-c")
    recon.f.pointer.current_decision_id = "d3"

    second = facade.evaluate(TASK_ID)

    assert second.authoritative_decision_id == "d3"
    assert second.reconciliation_operation_id is not None
    assert second.remediation_operation_id == second.reconciliation_operation_id
    assert len(recon.results.history(TASK_ID)) == 2
