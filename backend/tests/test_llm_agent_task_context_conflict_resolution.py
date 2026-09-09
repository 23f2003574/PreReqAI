import pytest

from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_conflict_resolution import (
    ContextConflictResolutionResult,
    InvalidConflictResolutionError,
    LLMAgentTaskContextConflictResolver,
)
from backend.agent_task_context_reconciliation import LLMAgentTaskContextReconciler
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.agent_policy_engine import DENY, LLMAgentPolicyService
from backend.llm.context_provenance import LLMContextProvenance
from backend.llm.project_context import LLMProjectContextService


def _task_context_service():
    return LLMAgentTaskContextService()


def _resolver_svc():
    return _task_context_service()


def _version_conflict(context_id, stored_priority=False, fresh_priority=False, fresh_entry=True):
    stored_entry = {"context_id": context_id, "content": "stored content", "context_type": "fact", "scope_id": "scope-1"}
    if stored_priority:
        stored_entry["metadata"] = {"priority": "high"}
    fresh = None
    if fresh_entry:
        fresh = {"context_id": context_id, "content": "fresh content", "context_type": "fact", "scope_id": "scope-1"}
        if fresh_priority:
            fresh["metadata"] = {"priority": "high"}
    return {
        "context_id": context_id,
        "stored_entry": stored_entry,
        "fresh_entry": fresh,
        "stored_provenance": LLMContextProvenance(
            context_id=context_id, source_type="project_context", source_id=context_id, excerpt="stored"
        ),
        "fresh_provenance": LLMContextProvenance(
            context_id=context_id, source_type="project_context", source_id=context_id, excerpt="fresh"
        )
        if fresh_entry
        else None,
    }


def _authority_conflict(context_id, reason="denied by policy xyz"):
    return {
        "context_id": context_id,
        "reason": f"context {context_id!r} {reason}" if "denied" in reason else reason,
        "entry": {"context_id": context_id, "content": "denied content", "context_type": "fact", "scope_id": "scope-1"},
        "provenance": LLMContextProvenance(
            context_id=context_id, source_type="project_context", source_id=context_id, excerpt="x"
        ),
    }


def _resolver_instance():
    return LLMAgentTaskContextConflictResolver(_task_context_service())


# --- higher-priority source wins when precedence exists ---------------------------------


def test_stored_priority_wins_over_fresh():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflict = _version_conflict("ctx-1", stored_priority=True)
    result = resolver.resolve(task_context.task_id, [conflict])

    assert isinstance(result, ContextConflictResolutionResult)
    assert result.decisions[0]["decision"] == "kept_stored"
    resolved_ids = {item["context_id"] for item in result.resolved}
    assert "ctx-1" in resolved_ids
    resolved_entry = next(item for item in result.resolved if item["context_id"] == "ctx-1")
    assert resolved_entry["entry"]["content"] == "stored content"
    discarded_entry = next(item for item in result.discarded_sources if item["context_id"] == "ctx-1")
    assert discarded_entry["entry"]["content"] == "fresh content"


# --- explicit task constraint is preserved ----------------------------------------------


def test_task_constraints_are_never_touched():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="do work", constraints=["read-only", "no-write"]
    )
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    resolver.resolve(task_context.task_id, [_version_conflict("ctx-1")])

    refreshed = task_context_service.get(task_context.task_id)
    assert refreshed.constraints == ["read-only", "no-write"]


# --- freshness/authority rules are respected ----------------------------------------------


def test_fresh_source_wins_by_default():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, [_version_conflict("ctx-1")])

    assert result.decisions[0]["decision"] == "kept_fresh"
    resolved_entry = next(item for item in result.resolved if item["context_id"] == "ctx-1")
    assert resolved_entry["entry"]["content"] == "fresh content"


def test_authority_violation_is_discarded():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, [_authority_conflict("ctx-1")])

    assert result.decisions[0]["decision"] == "discarded_unauthorized"
    assert result.resolved == []
    discarded_ids = {item["context_id"] for item in result.discarded_sources}
    assert "ctx-1" in discarded_ids


# --- unresolvable conflicts remain unresolved -----------------------------------------------


def test_both_sides_high_priority_is_unresolved():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflict = _version_conflict("ctx-1", stored_priority=True, fresh_priority=True)
    result = resolver.resolve(task_context.task_id, [conflict])

    assert result.unresolved_conflicts == [conflict]
    assert result.resolved == []
    assert result.decisions == []


def test_no_fresh_entry_is_unresolved():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflict = _version_conflict("ctx-1", fresh_entry=False)
    result = resolver.resolve(task_context.task_id, [conflict])

    assert result.unresolved_conflicts == [conflict]


def test_authority_conflict_without_denial_text_is_unresolved():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflict = _authority_conflict("ctx-1", reason="not a recognized rule violation")
    result = resolver.resolve(task_context.task_id, [conflict])

    assert result.unresolved_conflicts == [conflict]


def test_scope_mismatch_is_unresolved():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflict = _version_conflict("ctx-1")
    conflict["fresh_entry"]["scope_id"] = "scope-2"
    result = resolver.resolve(task_context.task_id, [conflict])

    assert result.unresolved_conflicts == [conflict]
    assert "ctx-1" in result.reasons
    assert "scope" in result.reasons["ctx-1"]


# --- provenance is retained for both sides -------------------------------------------------


def test_provenance_retained_for_both_resolved_and_discarded():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, [_version_conflict("ctx-1")])

    resolved_entry = next(item for item in result.resolved if item["context_id"] == "ctx-1")
    discarded_entry = next(item for item in result.discarded_sources if item["context_id"] == "ctx-1")
    assert resolved_entry["provenance"] is not None
    assert discarded_entry["provenance"] is not None
    assert resolved_entry["provenance"].excerpt == "fresh"
    assert discarded_entry["provenance"].excerpt == "stored"


def test_provenance_retained_for_discarded_authority_violation():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, [_authority_conflict("ctx-1")])

    discarded_entry = next(item for item in result.discarded_sources if item["context_id"] == "ctx-1")
    assert discarded_entry["provenance"] is not None


# --- identical inputs produce identical decisions --------------------------------------------


def test_identical_inputs_produce_identical_results():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    conflicts = [_version_conflict("ctx-1"), _authority_conflict("ctx-2")]
    first = resolver.resolve(task_context.task_id, conflicts)
    second = resolver.resolve(task_context.task_id, conflicts)

    assert first == second


# --- no stored context is mutated ------------------------------------------------------------


def test_resolution_is_side_effect_free():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)
    before = task_context_service.get(task_context.task_id)

    resolver.resolve(task_context.task_id, [_version_conflict("ctx-1"), _authority_conflict("ctx-2")])

    assert task_context_service.get(task_context.task_id) == before


# --- end-to-end with the real reconciler ------------------------------------------------------


def test_end_to_end_with_real_reconciler_conflicts():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-ctx", [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": context.context_id}}]
    )

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )

    task_resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, policy_service=policy_service
    )
    reconciler = LLMAgentTaskContextReconciler(task_context_service, task_resolver, policy_service=policy_service)
    reconciliation = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")
    assert reconciliation.conflicts  # sanity: reconciliation actually found one

    conflict_resolver = LLMAgentTaskContextConflictResolver(task_context_service)
    result = conflict_resolver.resolve(task_context.task_id, reconciliation.conflicts)

    discarded_ids = {item["context_id"] for item in result.discarded_sources}
    assert context.context_id in discarded_ids


# --- invalid input is rejected ------------------------------------------------------------------


def test_invalid_task_id_rejected():
    resolver = _resolver_instance()
    with pytest.raises(InvalidConflictResolutionError):
        resolver.resolve("", [])


def test_invalid_conflicts_type_rejected():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextConflictResolver(task_context_service)

    with pytest.raises(InvalidConflictResolutionError):
        resolver.resolve(task_context.task_id, "not-a-list")


def test_unknown_task_id_propagates():
    resolver = _resolver_instance()
    with pytest.raises(UnknownTaskContextError):
        resolver.resolve("missing-task", [])
