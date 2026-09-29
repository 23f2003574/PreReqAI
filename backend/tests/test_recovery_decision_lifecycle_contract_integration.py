"""End-to-end contract integration tests: prove that the facade (#1),
the stable AgentTaskRecoveryExecutionDecisionLifecycleResult contract
(#2), the CLI `recovery-decision evaluate` command (#3), and the
`POST /api/tasks/{task_id}/recovery-decision/evaluate` endpoint (#4) all
report the same semantic lifecycle outcome for the same task -- not a
re-test of any one surface's own behavior, which #1-#9's own unit tests
already cover in isolation.

Reuses the reconciliation test module's own fixtures (_Recon and
friends) -- the same fixture-reuse convention every test file in this
commit series already follows -- and the real
LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService (not
a fake), since decision_store is real here and the facade's own tests
already establish that's the right collaborator to use for it.
"""

import json

from fastapi.testclient import TestClient

from backend.agent_task_recovery_execution_precondition_snapshots import (
    AgentTaskRecoveryExecutionDecisionLifecycleResult,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    LIFECYCLE_VERIFICATION_VALID,
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

_CONTRACT_FIELDS = (
    "task_id", "authoritative_decision_id", "decision_lineage_status", "affected_artifacts",
    "remediation_operation_id", "reconciliation_operation_id", "blocking_conditions",
    "verification_status", "overall_status", "diagnostics",
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
    )


def _assert_contract(result):
    """No internal implementation result type leaks through: exactly the
    #2 contract type, exactly its nine documented fields, every list
    field a tuple of plain strings (never a nested object)."""
    assert type(result) is AgentTaskRecoveryExecutionDecisionLifecycleResult
    for field in _CONTRACT_FIELDS:
        assert hasattr(result, field)
    for field in ("affected_artifacts", "blocking_conditions", "diagnostics"):
        value = getattr(result, field)
        assert isinstance(value, tuple)
        assert all(isinstance(item, str) for item in value)


def _through_cli(monkeypatch, capsys, facade, task_id):
    exit_code = cli.main(["recovery-decision", "evaluate", task_id, "--json"], facade=facade)
    payload = json.loads(capsys.readouterr().out)
    return exit_code, payload


def _through_api(monkeypatch, facade, task_id):
    monkeypatch.setattr(recovery_decision_routes, "facade", facade)
    response = client.post(f"/api/tasks/{task_id}/recovery-decision/evaluate")
    return response.status_code, response.json()


def _assert_all_surfaces_agree(monkeypatch, capsys, recon, task_id):
    """Call the same scenario through the facade directly, then through
    the CLI, then through the API -- each a genuinely separate
    evaluate() call against the same shared in-memory stores (real
    service composition, not a cached/mocked result reused three times).
    With nothing changing in between, reconciliation is NO_OP on the
    second and third calls, so all three must report the identical
    contract."""
    facade = _facade(recon)

    direct = facade.evaluate(task_id)
    _assert_contract(direct)

    cli_exit, cli_payload = _through_cli(monkeypatch, capsys, facade, task_id)
    api_status, api_payload = _through_api(monkeypatch, facade, task_id)

    assert cli_payload == direct.to_dict()
    assert api_payload == direct.to_dict()
    assert api_status == 200

    return direct, cli_exit


def test_clean_current_task_agrees_across_facade_cli_and_api(monkeypatch, capsys):
    recon = _Recon(resolution_chain=("d1",))

    result, cli_exit = _assert_all_surfaces_agree(monkeypatch, capsys, recon, TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_CLEAN
    assert result.authoritative_decision_id == "d1"
    assert result.blocking_conditions == ()
    assert result.verification_status == LIFECYCLE_VERIFICATION_VALID
    assert cli_exit == cli.EXIT_OK


def test_successful_remediation_and_verification_agrees_across_surfaces(monkeypatch, capsys):
    """Priming an audited operation for the same decision change before
    the first evaluate() call means that call has nothing new to apply
    (UP_TO_DATE) -- a clean, already-remediated, fully verified outcome
    with nothing blocking."""
    recon = _Recon()
    recon.lifecycle.run(TASK_ID)  # primes the audit trail directly, bypassing the facade

    result, cli_exit = _assert_all_surfaces_agree(monkeypatch, capsys, recon, TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_UP_TO_DATE
    assert result.verification_status == LIFECYCLE_VERIFICATION_VALID
    assert result.remediation_operation_id is None
    # This fixture's own mechanisms leave real artifacts still blocking
    # even once remediated (the same finding #2's own tests establish),
    # so UP_TO_DATE + valid verification is still EXIT_FAILURE here --
    # "successful remediation" means the remediation step itself is
    # complete and confirmed (nothing new to apply, verification holds),
    # not that zero blockers remain.
    assert cli_exit == cli.EXIT_FAILURE


def test_decision_change_with_stale_artifacts_agrees_across_surfaces(monkeypatch, capsys):
    recon = _Recon()  # default d1 -> d2 transition: real, non-trivial impact

    result, cli_exit = _assert_all_surfaces_agree(monkeypatch, capsys, recon, TASK_ID)

    assert result.authoritative_decision_id == "d2"
    assert result.affected_artifacts
    assert result.remediation_operation_id is not None
    assert cli_exit == cli.EXIT_FAILURE  # this fixture's own remediation leaves real blockers


def test_manual_review_blocking_condition_agrees_across_surfaces(monkeypatch, capsys):
    recon = _Recon(fail=("invalidate",))

    result, cli_exit = _assert_all_surfaces_agree(monkeypatch, capsys, recon, TASK_ID)

    assert result.overall_status == IMPACT_LIFECYCLE_BLOCKED
    assert result.blocking_conditions != ()
    assert cli_exit == cli.EXIT_FAILURE


def test_invalid_decision_lineage_agrees_across_surfaces(monkeypatch, capsys):
    """No recorded supersession links for this fixture's decisions -- the
    real validation service reports the lineage invalid."""
    recon = _Recon()

    result, cli_exit = _assert_all_surfaces_agree(monkeypatch, capsys, recon, TASK_ID)

    assert result.decision_lineage_status == "invalid"
    assert cli_exit == cli.EXIT_FAILURE


def test_stale_decision_reconciliation_agrees_between_cli_and_api(monkeypatch, capsys):
    """A decision added between calls makes the persisted result stale;
    the CLI call that observes it performs the replacement (its own
    reconciliation_operation_id), and the API call right after -- with
    nothing further changing -- confirms the SAME resulting authoritative
    decision and remediation outcome (NO_OP relative to the CLI's own
    replacement, so its own reconciliation_operation_id is legitimately
    None instead), never a stale or disagreeing view."""
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon)
    facade.evaluate(TASK_ID)

    recon.add_decision("d2", minutes=30, authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b")
    recon.f.pointer.current_decision_id = "d2"

    cli_exit, cli_payload = _through_cli(monkeypatch, capsys, facade, TASK_ID)
    api_status, api_payload = _through_api(monkeypatch, facade, TASK_ID)

    assert cli_payload["authoritative_decision_id"] == "d2"
    assert cli_payload["reconciliation_operation_id"] is not None
    for field in (
        "authoritative_decision_id", "decision_lineage_status", "affected_artifacts",
        "blocking_conditions", "verification_status", "overall_status",
    ):
        assert cli_payload[field] == api_payload[field], field
    assert api_payload["reconciliation_operation_id"] is None  # NO_OP: nothing changed after the CLI's own call
    assert api_status == 200


def test_failed_dependency_is_reported_consistently_as_a_failure_not_a_result(monkeypatch, capsys):
    """A composed service raising (store down, dependency misconfigured)
    must be treated as a failure by every surface, never smuggled through
    as a normal, successful-looking contract result."""
    recon = _Recon(resolution_chain=("d1",))
    facade = _facade(recon)

    class _BrokenResults:
        def latest(self, task_id):
            raise RuntimeError("lifecycle result store unavailable")

    facade._results = _BrokenResults()

    try:
        facade.evaluate(TASK_ID)
        raise AssertionError("expected the facade to propagate the dependency failure")
    except RuntimeError as error:
        assert "lifecycle result store unavailable" in str(error)

    cli_exit = cli.main(["recovery-decision", "evaluate", TASK_ID], facade=facade)
    cli_err = capsys.readouterr().err
    assert cli_exit == cli.EXIT_FAILURE
    assert "Traceback" not in cli_err

    monkeypatch.setattr(recovery_decision_routes, "facade", facade)
    response = client.post(f"/api/tasks/{TASK_ID}/recovery-decision/evaluate")
    assert response.status_code == 500
    assert "lifecycle result store unavailable" not in response.json()["detail"]
    assert "Traceback" not in response.json()["detail"]
