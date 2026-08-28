import dataclasses

import pytest

from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_refresh import InvalidRefreshPlanError, LLMContextRefreshService
from backend.llm.context_refresh_execution import (
    FAILED,
    PARTIAL,
    ROLLED_BACK,
    SUCCEEDED,
    InvalidRollbackError,
    LLMContextRefreshExecutionService,
    NoApprovedActionsError,
    UnknownExecutionError,
)
from backend.llm.context_version import LLMContextVersionService
from backend.llm.project_context import LLMProjectContextService
from backend.session import InMemoryResearchArtifactStore, ResearchArtifact, ResearchArtifactType


def _pipeline():
    context_service = LLMProjectContextService()
    version_service = LLMContextVersionService(context_service)
    artifact_store = InMemoryResearchArtifactStore()
    provenance_service = LLMContextProvenanceService(
        context_service, version_service=version_service, artifact_store=artifact_store
    )
    freshness_service = LLMContextFreshnessService(context_service, provenance_service, None)
    refresh_service = LLMContextRefreshService(freshness_service)
    execution_service = LLMContextRefreshExecutionService(refresh_service)
    return {
        "context": context_service,
        "version": version_service,
        "artifact_store": artifact_store,
        "provenance": provenance_service,
        "refresh": refresh_service,
        "execution": execution_service,
    }


def _make_stale_context_version(p, scope_id="notebook-1"):
    context = p["context"].create(scope_id, "summary", "v1 content")
    v1 = p["version"].snapshot(context.context_id)
    p["provenance"].attach(
        context.context_id,
        {
            "source_type": "context_version",
            "source_id": context.context_id,
            "source_version": v1.version,
            "excerpt": "captured v1",
        },
    )
    p["context"].update(context.context_id, "v2 content")
    v2 = p["version"].snapshot(context.context_id)
    return context, v1, v2


def test_successful_refresh():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)

    assert execution.status == SUCCEEDED
    assert execution.refreshed_context_ids == (context.context_id,)
    assert execution.completed_at is not None
    assert execution.completed_at >= execution.created_at

    assert p["context"].get(context.context_id).content == "v2 content"
    assert p["execution"].status(execution.execution_id) == execution


def test_invalid_or_unapproved_plan():
    p = _pipeline()

    # a plan that has since become fresh is no longer valid to execute
    context, v1, v2 = _make_stale_context_version(p)
    plan = p["refresh"].plan(context.context_id)
    p["provenance"].attach(
        context.context_id,
        {
            "source_type": "context_version",
            "source_id": context.context_id,
            "source_version": v2.version,
            "excerpt": "caught up to v2",
        },
    )
    with pytest.raises(InvalidRefreshPlanError):
        p["execution"].execute(plan.plan_id)

    # an unresolvable plan has no approved actions to execute
    unresolvable_context = p["context"].create("notebook-1", "fact", "no provenance yet")
    unresolvable_plan = p["refresh"].plan(unresolvable_context.context_id)
    with pytest.raises(NoApprovedActionsError):
        p["execution"].execute(unresolvable_plan.plan_id)


def test_version_creation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    history_before = p["version"].history(context.context_id)
    plan = p["refresh"].plan(context.context_id)
    p["execution"].execute(plan.plan_id)

    history_after = p["version"].history(context.context_id)

    assert len(history_after) > len(history_before)
    # nothing already recorded was destroyed
    assert [v.version for v in history_before] == [v.version for v in history_after[: len(history_before)]]
    assert history_after[-1].content == "v2 content"


def test_provenance_preservation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    sources_before = p["provenance"].sources(context.context_id)
    plan = p["refresh"].plan(context.context_id)
    p["execution"].execute(plan.plan_id)

    sources_after = p["provenance"].sources(context.context_id)

    assert len(sources_after) == len(sources_before) + 1
    assert sources_after[: len(sources_before)] == sources_before  # old records untouched
    newest = sources_after[-1]
    assert newest.source_type == "context_version"
    assert newest.source_id == context.context_id
    assert newest.source_version == v2.version


def test_partial_refresh_failure():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)
    safe_action = plan.refresh_actions[0]
    secret_action = {
        "source_type": "research_artifact",
        "source_id": "artifact-with-a-secret",
        "current_version": 1,
        "current_content": "api_key=sk-abcdefghijklmnopqrstuvwxyz",
    }
    p["artifact_store"].save(
        ResearchArtifact(
            id="artifact-with-a-secret",
            session_id="session-1",
            object_id="paper-1",
            artifact_type=ResearchArtifactType.SUMMARY,
            content="api_key=sk-abcdefghijklmnopqrstuvwxyz",
            version=1,
        )
    )
    # Commit #10's plan() only ever proposes one action today (the context's
    # single latest provenance record); this hand-built second action
    # exercises LLMContextRefreshExecutionService's own per-action handling,
    # which is written to process a list of actions independently.
    two_action_plan = dataclasses.replace(plan, refresh_actions=(safe_action, secret_action))
    p["refresh"]._plans[plan.plan_id] = two_action_plan

    execution = p["execution"].execute(plan.plan_id)

    assert execution.status == PARTIAL
    assert execution.refreshed_context_ids == (context.context_id,)
    # the successful action's content survives; the secret one never applied
    assert p["context"].get(context.context_id).content == "v2 content"


def test_rollback():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)
    original_content = p["context"].get(context.context_id).content

    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)
    assert p["context"].get(context.context_id).content == "v2 content"

    rolled_back = p["execution"].rollback(execution.execution_id)

    assert rolled_back.status == ROLLED_BACK
    assert p["context"].get(context.context_id).content == original_content
    assert p["execution"].status(execution.execution_id).status == ROLLED_BACK

    # rollback itself becomes new history, not a rewrite
    assert p["version"].latest(context.context_id).content == original_content

    # cannot roll back twice
    with pytest.raises(InvalidRollbackError):
        p["execution"].rollback(execution.execution_id)

    with pytest.raises(UnknownExecutionError):
        p["execution"].rollback("not-a-real-execution-id")


def test_existing_context_preservation_on_total_failure():
    p = _pipeline()

    artifact = p["artifact_store"].save(
        ResearchArtifact(
            session_id="session-1",
            object_id="paper-1",
            artifact_type=ResearchArtifactType.SUMMARY,
            content="api_key=sk-abcdefghijklmnopqrstuvwxyz",
        )
    )
    context = p["context"].create("notebook-1", "summary", "original safe content")
    p["provenance"].attach(
        context.context_id,
        {
            "source_type": "research_artifact",
            "source_id": artifact.id,
            "source_version": artifact.version,
            "excerpt": "from artifact v1",
        },
    )
    # artifact changes to a new, secret-laden version -- makes the context
    # stale, but the refresh itself cannot apply
    updated_artifact = dataclasses.replace(artifact, version=artifact.version + 1)
    p["artifact_store"].save(updated_artifact)

    before = p["context"].get(context.context_id)
    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)

    assert execution.status == FAILED
    assert execution.refreshed_context_ids == ()

    after = p["context"].get(context.context_id)
    assert after.content == before.content == "original safe content"
    assert after.updated_at == before.updated_at
