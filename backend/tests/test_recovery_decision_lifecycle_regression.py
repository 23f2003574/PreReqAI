"""Regression lock-down for the recovery execution decision lifecycle's
highest-risk invariants, across the facade (#1), the #2 contract, the
CLI (#3), and the API (#4).

Reuses the reconciliation test module's own fixtures (_Recon and
friends) and the same fake-supersession-validation-service pattern
#6/#7's own tests already established for constructing a genuinely
clean, all-valid scenario -- no new fixtures, no second integration
suite. Each test asserts an invariant a future change could silently
break, not an implementation detail already covered by #1-#10's own
unit/integration tests.
"""

import json
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_VALIDATION_FAILED,
    INTEGRITY_INVALID,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_CONFLICT,
    SUPERSESSION_VALID,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
)

import backend.api.recovery_decision_routes as recovery_decision_routes
import backend.cli as cli
from backend.main import app

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)

client = TestClient(app)


def _fake_supersession(status=SUPERSESSION_VALID):
    return SimpleNamespace(
        validate=lambda task_id: SimpleNamespace(status=status, issues=(), chain=(), terminal_decision_id=None),
    )


def _facade(recon, supersession_validation_service=None):
    supersession_validation = supersession_validation_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=recon.f.decision_store,
    )
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=supersession_validation,
        lifecycle_service=recon.lifecycle,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
        reconciliation_service=recon.service,
    )


def test_stale_decisions_never_reach_execution_as_current():
    """d1 has been superseded by d2 -- evaluate() must always report d2
    as authoritative, never fall back to the older d1."""
    recon = _Recon()
    result = _facade(recon).evaluate(TASK_ID)

    assert result.authoritative_decision_id == "d2"
    assert result.authoritative_decision_id != "d1"


def test_superseded_decisions_remain_immutable():
    """The decision store is append-only -- evaluating a task must never
    modify a previously recorded decision's own fields."""
    recon = _Recon()
    before = recon.f.decision_store.get("d1")

    _facade(recon).evaluate(TASK_ID)

    after = recon.f.decision_store.get("d1")
    assert before == after


def test_conflicting_lineage_remains_blocking():
    """A CONFLICT resolution state must never produce an authoritative
    decision or a successful outcome."""
    recon = _Recon()
    recon.resolution.resolve = lambda task_id: SimpleNamespace(
        resolution_state=RESOLUTION_CONFLICT, terminal_decision_id=None, chain=("d1", "d2"),
    )

    result = _facade(recon).evaluate(TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_UNRESOLVED
    assert result.authoritative_decision_id is None


def test_stale_artifacts_cannot_be_treated_as_executable():
    """When an invalidation mechanism fails, the artifacts it was
    supposed to resolve must remain reported as stale/blocking -- never
    silently dropped or treated as if they were fine."""
    recon = _Recon(fail=("invalidate",))
    result = _facade(recon).evaluate(TASK_ID)

    assert result.overall_status != IMPACT_LIFECYCLE_REMEDIATED
    assert result.blocking_conditions != ()


def test_manual_review_remains_blocking():
    """An item the plan marks manual_review must stay a blocking
    condition and must never let the lifecycle report success, however
    the rest of the plan resolves."""
    recon = _Recon()
    real_plan = recon.f.planner.plan

    def with_manual_review(task_id, staleness):
        plan = real_plan(task_id, staleness)
        manual = replace(
            plan.items[0], artifact_id="mystery:d1", artifact_type="mystery",
            action="manual_review", mechanism=None, execution_blocked=True, depends_on=(),
        )
        return replace(plan, items=plan.items + (manual,))

    recon.f.planner.plan = with_manual_review

    result = _facade(recon).evaluate(TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_VALIDATION_FAILED
    assert "mystery:d1" in result.blocking_conditions


def test_failed_verification_cannot_produce_a_successful_lifecycle():
    """A lifecycle result whose verification comes back invalid must
    never be reported as successful by any consuming surface."""
    recon = _Recon(integrity=INTEGRITY_INVALID)
    result = _facade(recon).evaluate(TASK_ID)

    assert result.verification_status != LIFECYCLE_VERIFICATION_VALID

    exit_code = cli.main(["recovery-decision", "evaluate", TASK_ID], facade=_facade(recon))
    assert exit_code == cli.EXIT_FAILURE


def test_failed_remediation_is_preserved_in_lifecycle_results():
    """A blocked remediation outcome must actually be persisted, not
    discarded -- the record a future diagnose()/reconcile() call reads
    back must show the same failure."""
    recon = _Recon(fail=("invalidate",))
    _facade(recon).evaluate(TASK_ID)

    persisted = recon.results.latest(TASK_ID)
    assert persisted is not None
    assert persisted.status == IMPACT_LIFECYCLE_BLOCKED
    assert persisted.blocking_artifacts != ()
    assert recon.results.history(TASK_ID)[-1] == persisted


def test_reconciliation_never_overwrites_historical_results():
    """A REPLACED reconciliation must append a new lifecycle result, not
    mutate or remove the one it is replacing."""
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon)
    facade.evaluate(TASK_ID)
    first = recon.results.latest(TASK_ID)

    recon.add_decision("d2", minutes=30, authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b")
    recon.f.pointer.current_decision_id = "d2"
    facade.evaluate(TASK_ID)

    assert recon.results.get(TASK_ID, first.result_id) == first
    history = recon.results.history(TASK_ID)
    assert len(history) == 2
    assert history[0] == first


def test_repeated_lifecycle_evaluation_is_idempotent_where_expected():
    """Two evaluate() calls with nothing changed in between must never
    run remediation twice or produce a different contract result."""
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon)

    first = facade.evaluate(TASK_ID)
    history_after_first = recon.results.history(TASK_ID)
    second = facade.evaluate(TASK_ID)

    assert recon.results.history(TASK_ID) == history_after_first
    assert second.to_dict() == first.to_dict()


def test_cli_and_api_preserve_the_same_semantic_status_as_the_facade(monkeypatch, capsys):
    recon = _Recon(fail=("invalidate",))
    facade = _facade(recon)

    direct = facade.evaluate(TASK_ID)

    cli_exit = cli.main(["recovery-decision", "evaluate", TASK_ID, "--json"], facade=facade)
    cli_payload = json.loads(capsys.readouterr().out)

    monkeypatch.setattr(recovery_decision_routes, "facade", facade)
    response = client.post(f"/api/tasks/{TASK_ID}/recovery-decision/evaluate")

    assert cli_exit == cli.EXIT_FAILURE
    assert cli_payload["overall_status"] == direct.overall_status
    assert response.json()["overall_status"] == direct.overall_status
    assert response.json()["blocking_conditions"] == list(direct.blocking_conditions)


def test_full_happy_path_reaches_a_successful_public_result(monkeypatch, capsys):
    """authoritative decision -> valid lineage -> no stale artifacts ->
    lifecycle verification -> a successful public result, agreeing
    across the facade, CLI, and API."""
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon, supersession_validation_service=_fake_supersession(SUPERSESSION_VALID))

    result = facade.evaluate(TASK_ID)

    assert result.authoritative_decision_id == "d1"
    assert result.decision_lineage_status == SUPERSESSION_VALID
    assert result.affected_artifacts == ()
    assert result.verification_status == LIFECYCLE_VERIFICATION_VALID
    assert result.blocking_conditions == ()
    assert result.overall_status in (IMPACT_LIFECYCLE_REMEDIATED, "clean")

    cli_exit = cli.main(["recovery-decision", "evaluate", TASK_ID, "--json"], facade=facade)
    capsys.readouterr()
    assert cli_exit == cli.EXIT_OK

    monkeypatch.setattr(recovery_decision_routes, "facade", facade)
    response = client.post(f"/api/tasks/{TASK_ID}/recovery-decision/evaluate")
    assert response.status_code == 200
    assert response.json()["blocking_conditions"] == []
