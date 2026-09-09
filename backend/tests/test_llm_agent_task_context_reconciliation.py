import pytest

from backend.agent_policy_engine import DENY, LLMAgentPolicyService
from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_reconciliation import (
    ContextReconciliationResult,
    InvalidContextReconciliationError,
    LLMAgentTaskContextReconciler,
    TaskContextReconciliationScopeMismatchError,
)
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_snapshot import LLMContextSnapshotService
from backend.llm.project_context import LLMProjectContextService


def _freshness_stack(project_context_service):
    provenance_service = LLMContextProvenanceService(project_context_service)
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(project_context_service, provenance_service, snapshot_service)
    return provenance_service, freshness_service


def _task_context_service():
    return LLMAgentTaskContextService()


# --- identical contexts produce no changes -----------------------------------------------


def test_identical_contexts_produce_no_changes():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(
        task_context_service, resolver, project_context_service=project_context_service
    )

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert isinstance(result, ContextReconciliationResult)
    assert result.added == []
    assert result.removed == []
    assert result.changed == []
    assert result.conflicts == []
    assert any(item["context_id"] == context.context_id for item in result.unchanged)


# --- new sources appear as additions -------------------------------------------------------


def test_new_source_appears_as_addition():
    project_context_service = LLMProjectContextService()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    added_ids = {item["context_id"] for item in result.added}
    assert on_topic.context_id in added_ids
    matching = next(item for item in result.added if item["context_id"] == on_topic.context_id)
    assert matching["provenance"] is not None


# --- missing sources appear as removals -----------------------------------------------------


def test_missing_source_appears_as_removal():
    project_context_service = LLMProjectContextService()

    task_context_service = _task_context_service()
    # a stored entry whose context_id was never (or is no longer) registered
    # in the project context store at all, so the resolver can never find it
    stale_entry = {"context_id": "gone-1", "content": "no longer exists", "context_type": "fact", "scope_id": "scope-1"}
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="unrelated objective with no matches",
        relevant_context=[stale_entry],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(
        task_context_service, resolver, project_context_service=project_context_service
    )

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    removed_ids = {item["context_id"] for item in result.removed}
    assert "gone-1" in removed_ids


def test_no_project_context_service_never_reports_removed():
    task_context_service = _task_context_service()
    stale_entry = {"context_id": "gone-1", "content": "no longer exists", "context_type": "fact", "scope_id": "scope-1"}
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="unrelated objective with no matches",
        relevant_context=[stale_entry],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert result.removed == []


# --- changed versions are detected -----------------------------------------------------------


def test_changed_content_is_detected():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "original content about notebooks")

    task_context_service = _task_context_service()
    stale_dict = context.to_dict()
    stale_dict["content"] = "stale cached copy of the content"
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="original content about notebooks", relevant_context=[stale_dict]
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(
        task_context_service, resolver, project_context_service=project_context_service
    )

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    changed_ids = {item["context_id"] for item in result.changed}
    assert context.context_id in changed_ids
    matching = next(item for item in result.changed if item["context_id"] == context.context_id)
    assert matching["stored_entry"]["content"] == "stale cached copy of the content"
    assert matching["fresh_entry"]["content"] == "original content about notebooks"


def test_no_project_context_service_never_reports_changed():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "original content about notebooks")

    task_context_service = _task_context_service()
    stale_dict = context.to_dict()
    stale_dict["content"] = "stale cached copy of the content"
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="original content about notebooks", relevant_context=[stale_dict]
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert result.changed == []


# --- stale sources are reported ----------------------------------------------------------------


def test_stale_sources_are_reported():
    project_context_service = LLMProjectContextService()
    provenance_service, freshness_service = _freshness_stack(project_context_service)

    context = project_context_service.create("scope-1", "fact", "original content")
    recorded_provenance = provenance_service.attach(
        context.context_id, {"source_type": "project_context", "source_id": context.context_id, "excerpt": "x"}
    )
    project_context_service.update(context.context_id, "revised content, after provenance was recorded")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="original content",
        relevant_context=[context.to_dict()],
        provenance=[recorded_provenance],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver, freshness_service=freshness_service)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert context.context_id in result.stale


def test_no_freshness_service_never_reports_stale():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "content")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="content", relevant_context=[context.to_dict()]
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert result.stale == []


# --- scope/authorization violations are surfaced ------------------------------------------------


def test_authorization_violation_is_surfaced_as_conflict():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-ctx",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": context.context_id}}],
    )

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, policy_service=policy_service
    )
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver, policy_service=policy_service)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    conflict_ids = {item["context_id"] for item in result.conflicts}
    assert context.context_id in conflict_ids
    removed_ids = {item["context_id"] for item in result.removed}
    assert context.context_id in removed_ids  # deliberate overlap
    matching = next(item for item in result.conflicts if item["context_id"] == context.context_id)
    assert "denied" in matching["reason"]


def test_no_policy_service_never_reports_conflicts():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-ctx",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": context.context_id}}],
    )

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, policy_service=policy_service
    )
    # policy_service deliberately NOT wired into the reconciler itself
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    result = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert result.conflicts == []


def test_scope_mismatch_raises():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    with pytest.raises(TaskContextReconciliationScopeMismatchError):
        reconciler.reconcile(task_context.task_id, "agent-1", "scope-2")
    with pytest.raises(TaskContextReconciliationScopeMismatchError):
        reconciler.reconcile(task_context.task_id, "agent-2", "scope-1")


# --- reconciliation does not mutate stored context ------------------------------------------------


def test_reconciliation_is_side_effect_free():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )
    before_task = task_context_service.get(task_context.task_id)
    before_project = project_context_service.get(context.context_id)

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)
    reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert task_context_service.get(task_context.task_id) == before_task
    assert project_context_service.get(context.context_id) == before_project


def test_reconciliation_is_deterministic():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    first = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")
    second = reconciler.reconcile(task_context.task_id, "agent-1", "scope-1")

    assert [i["context_id"] for i in first.added] == [i["context_id"] for i in second.added]


# --- invalid input is rejected ---------------------------------------------------------------------


def test_invalid_identifiers_rejected():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    with pytest.raises(InvalidContextReconciliationError):
        reconciler.reconcile(task_context.task_id, "", "scope-1")
    with pytest.raises(InvalidContextReconciliationError):
        reconciler.reconcile(task_context.task_id, "agent-1", "")


def test_unknown_task_id_propagates():
    task_context_service = _task_context_service()
    resolver = LLMAgentTaskContextResolver(task_context_service)
    reconciler = LLMAgentTaskContextReconciler(task_context_service, resolver)

    with pytest.raises(UnknownTaskContextError):
        reconciler.reconcile("missing-task", "agent-1", "scope-1")
