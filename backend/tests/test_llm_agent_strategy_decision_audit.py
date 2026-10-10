from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import InMemoryLLMAgentMemoryStore, LLMAgentMemory, LLMAgentMemoryService
from backend.agent_strategy_application import CONTEXT_KEY, LLMAgentStrategyApplicator
from backend.agent_strategy_conflict_resolution import (
    EVIDENCE,
    UNRESOLVED,
    LLMAgentStrategyConflict,
    LLMAgentStrategyConflictDecision,
    LLMAgentStrategyConflictResolution,
)
from backend.agent_strategy_decision_audit import (
    APPLIED,
    CONFLICT_RESOLVED,
    REJECTED,
    SELECTED,
    InvalidDecisionTypeError,
    InvalidEvidenceError,
    LLMAgentStrategyDecisionAuditService,
    SecretEvidenceError,
    UnknownAgentStrategyDecisionError,
)
from backend.agent_strategy_library import LLMAgentStrategyService, UnknownAgentStrategyError
from backend.agent_strategy_scoring import LLMAgentStrategyScore
from backend.agent_strategy_selection import LLMAgentStrategySelection
from backend.llm.tool_execution import SUCCEEDED

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

_memory_counter = [0]


def _memory_service_with_strategy_service():
    """A real Commit #1 LLMAgentStrategyService, backed by a real
    LLMAgentMemoryService whose store already carries whatever memories
    _memory()/_strategy() below insert directly -- the full Commit #12
    tool-execution pipeline isn't needed here since Commit #11 never
    calls LLMAgentMemoryService.record(), only Commit #1's own
    get()/create(), which never touch plan_execution_service."""
    memory_store = InMemoryLLMAgentMemoryStore()
    memory_service = LLMAgentMemoryService(plan_execution_service=None, store=memory_store)
    strategy_service = LLMAgentStrategyService(memory_service)
    return memory_service, strategy_service


def _memory(memory_service, scope_id="notebook-1"):
    _memory_counter[0] += 1
    memory = LLMAgentMemory(
        scope_id=scope_id, execution_id=f"fake-execution-{_memory_counter[0]}", memory_type="strategy",
        content="proof", outcome=SUCCEEDED,
    )
    return memory_service.store.save(memory)


def _strategy(strategy_service, memory_service, scope_id="notebook-1", name="strategy"):
    memory = _memory(memory_service, scope_id=scope_id)
    return strategy_service.create(scope_id, name, f"{name} description", {"steps": ["a"]}, [memory.memory_id])


def _score(strategy_id, score=0.8, confidence=0.8, evidence_count=3, succeeded=3, failed=0):
    return LLMAgentStrategyScore(
        strategy_id=strategy_id, score=score, confidence=confidence, evidence_count=evidence_count,
        succeeded_count=succeeded, failed_count=failed, reason="test evidence", scored_at=NOW,
    )


def _selection(strategy, effectiveness, relevance_score=0.9):
    combined = round(0.5 * relevance_score + 0.5 * effectiveness.score, 6)
    return LLMAgentStrategySelection(
        strategy=strategy, relevance_score=relevance_score, effectiveness=effectiveness,
        combined_score=combined, reason="selected because it matched and performed well",
    )


def test_decision_recording():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)
    strategy = _strategy(strategy_service, memory_service)

    decision = audit_service.record(
        strategy.strategy_id, "task-1", SELECTED, "included", "matched the task well", score=0.9,
        evidence={"relevance_score": 0.9},
    )

    assert decision.decision_id is not None
    assert decision.strategy_id == strategy.strategy_id
    assert decision.execution_or_task_id == "task-1"
    assert decision.decision_type == SELECTED
    assert decision.decision == "included"
    assert decision.reason == "matched the task well"
    assert decision.score == 0.9
    assert decision.evidence == {"relevance_score": 0.9}
    assert decision.created_at is not None

    fetched = audit_service.get(decision.decision_id)
    assert fetched.decision_id == decision.decision_id


def test_selection_and_rejection_audit():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)

    winner_strategy = _strategy(strategy_service, memory_service, name="winner")
    loser_strategy = _strategy(strategy_service, memory_service, name="loser")

    selected = [_selection(winner_strategy, _score(winner_strategy.strategy_id, score=0.9))]
    audit_service.record_selection("task-1", selected)

    conflict = LLMAgentStrategyConflict(
        strategy_ids=(loser_strategy.strategy_id, winner_strategy.strategy_id),
        reason="both strategies share exclusive_group 'approach'",
    )
    decision = LLMAgentStrategyConflictDecision(
        conflict=conflict, winner_strategy_id=winner_strategy.strategy_id,
        loser_strategy_id=loser_strategy.strategy_id, resolution=EVIDENCE,
        reason="winner has stronger effectiveness score",
    )
    resolution = LLMAgentStrategyConflictResolution(selected=selected, conflicts=[decision])
    audit_service.record_conflict_resolution("task-1", resolution)

    winner_records = audit_service.list_for_strategy(winner_strategy.strategy_id)
    loser_records = audit_service.list_for_strategy(loser_strategy.strategy_id)

    assert [r.decision_type for r in winner_records] == [SELECTED, CONFLICT_RESOLVED]
    assert winner_records[1].decision == "won"

    assert [r.decision_type for r in loser_records] == [REJECTED]
    assert loser_records[0].decision == "lost_conflict"
    assert loser_records[0].reason == "winner has stronger effectiveness score"


def test_conflict_decision_audit_unresolved():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)

    strategy_a = _strategy(strategy_service, memory_service, name="strategy-a")
    strategy_b = _strategy(strategy_service, memory_service, name="strategy-b")

    conflict = LLMAgentStrategyConflict(
        strategy_ids=(strategy_a.strategy_id, strategy_b.strategy_id), reason="shared exclusive_group",
    )
    decision = LLMAgentStrategyConflictDecision(
        conflict=conflict, winner_strategy_id=None, loser_strategy_id=None, resolution=UNRESOLVED,
        reason="both strategies are explicitly required by context",
    )
    resolution = LLMAgentStrategyConflictResolution(selected=[], conflicts=[decision])

    records = audit_service.record_conflict_resolution("task-1", resolution)

    assert len(records) == 2
    assert {r.strategy_id for r in records} == {strategy_a.strategy_id, strategy_b.strategy_id}
    assert all(r.decision_type == CONFLICT_RESOLVED and r.decision == "unresolved" for r in records)
    # never silently discarded -- both flagged with the real reason
    assert all(r.reason == "both strategies are explicitly required by context" for r in records)


def test_application_audit():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)
    strategy = _strategy(strategy_service, memory_service)

    selection = _selection(strategy, _score(strategy.strategy_id))
    applied_context = LLMAgentStrategyApplicator().apply(None, [selection])

    records = audit_service.record_application("task-1", applied_context)

    assert len(records) == 1
    record = records[0]
    assert record.strategy_id == strategy.strategy_id
    assert record.decision_type == APPLIED
    assert record.decision == "applied"
    assert record.score == applied_context[CONTEXT_KEY][0]["combined_score"]
    assert record.evidence["provenance"]["source_memory_ids"] == strategy.source_memory_ids


def test_provenance():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)
    strategy = _strategy(strategy_service, memory_service)

    selection = _selection(strategy, _score(strategy.strategy_id, score=0.75, confidence=0.85, evidence_count=4))
    records = audit_service.record_selection("task-1", [selection])

    record = records[0]
    assert record.score == selection.combined_score
    assert record.evidence["relevance_score"] == selection.relevance_score
    assert record.evidence["effectiveness"]["score"] == selection.effectiveness.score
    assert record.evidence["effectiveness"]["confidence"] == selection.effectiveness.confidence
    assert record.reason == selection.reason


def test_scope_isolation():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)

    strategy_a = _strategy(strategy_service, memory_service, scope_id="notebook-1", name="strategy-a")
    strategy_b = _strategy(strategy_service, memory_service, scope_id="notebook-2", name="strategy-b")

    audit_service.record(strategy_a.strategy_id, "task-1", SELECTED, "included", "a reason")
    audit_service.record(strategy_b.strategy_id, "task-1", SELECTED, "included", "a reason")

    records_a = audit_service.list_for_strategy(strategy_a.strategy_id)
    records_b = audit_service.list_for_strategy(strategy_b.strategy_id)

    assert [r.strategy_id for r in records_a] == [strategy_a.strategy_id]
    assert [r.strategy_id for r in records_b] == [strategy_b.strategy_id]

    # both still discoverable from the shared task/execution id, each
    # correctly attributed to its own strategy
    for_task = audit_service.list_for_execution("task-1")
    assert {r.strategy_id for r in for_task} == {strategy_a.strategy_id, strategy_b.strategy_id}


def test_immutable_history():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)
    strategy = _strategy(strategy_service, memory_service)

    audit_service.record(strategy.strategy_id, "task-1", SELECTED, "included", "first look")
    audit_service.record(strategy.strategy_id, "task-1", CONFLICT_RESOLVED, "won", "beat a rival")
    audit_service.record(strategy.strategy_id, "task-2", APPLIED, "applied", "reused later")

    history = audit_service.list_for_strategy(strategy.strategy_id)

    assert [r.decision_type for r in history] == [SELECTED, CONFLICT_RESOLVED, APPLIED]
    # every earlier record is untouched by the later ones
    assert history[0].decision == "included"
    assert history[1].decision == "won"
    assert history[2].execution_or_task_id == "task-2"


def test_missing_strategy():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)

    with pytest.raises(UnknownAgentStrategyError):
        audit_service.record("missing-strategy", "task-1", SELECTED, "included", "a reason")

    with pytest.raises(UnknownAgentStrategyError):
        audit_service.list_for_strategy("missing-strategy")

    with pytest.raises(UnknownAgentStrategyDecisionError):
        audit_service.get("missing-decision")


def test_validation():
    memory_service, strategy_service = _memory_service_with_strategy_service()
    audit_service = LLMAgentStrategyDecisionAuditService(strategy_service)
    strategy = _strategy(strategy_service, memory_service)

    with pytest.raises(InvalidDecisionTypeError):
        audit_service.record(strategy.strategy_id, "task-1", "not-a-type", "included", "a reason")

    with pytest.raises(ValueError):
        audit_service.record(strategy.strategy_id, "task-1", SELECTED, "", "a reason")

    with pytest.raises(ValueError):
        audit_service.record(strategy.strategy_id, "task-1", SELECTED, "included", "")

    with pytest.raises(InvalidEvidenceError):
        audit_service.record(
            strategy.strategy_id, "task-1", SELECTED, "included", "a reason", evidence={"bad": object()}
        )

    with pytest.raises(SecretEvidenceError):
        audit_service.record(
            strategy.strategy_id, "task-1", SELECTED, "included", "a reason",
            evidence={"note": "api_key: sk-abcdefghijklmnop"},
        )
