import dataclasses

import pytest

from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_refresh import LLMContextRefreshService
from backend.llm.context_refresh_execution import LLMContextRefreshExecutionService
from backend.llm.context_refresh_orchestration import (
    ACTIVATED,
    NOOP_FRESH,
    PLANNING_FAILED,
    REFRESH_FAILED,
    VALIDATION_FAILED,
    ActivationRefusedError,
    LLMContextRefreshOrchestrationService,
)
from backend.llm.context_refresh_validation import LLMContextRefreshValidationService
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
    validation_service = LLMContextRefreshValidationService(execution_service, freshness_service)
    orchestration_service = LLMContextRefreshOrchestrationService(validation_service)
    return {
        "context": context_service,
        "version": version_service,
        "artifact_store": artifact_store,
        "provenance": provenance_service,
        "freshness": freshness_service,
        "refresh": refresh_service,
        "execution": execution_service,
        "validation": validation_service,
        "orchestration": orchestration_service,
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


def test_fresh_context_is_a_noop():
    p = _pipeline()

    context = p["context"].create("notebook-1", "summary", "v1 content")
    v1 = p["version"].snapshot(context.context_id)
    p["provenance"].attach(
        context.context_id,
        {
            "source_type": "context_version",
            "source_id": context.context_id,
            "source_version": v1.version,
            "excerpt": "already fresh",
        },
    )

    decision = p["orchestration"].refresh(context.context_id)

    assert decision.outcome == NOOP_FRESH
    assert decision.plan_id is None
    assert decision.execution_id is None
    assert decision.validation_id is None
    assert p["context"].get(context.context_id).content == "v1 content"


def test_stale_context_successful_refresh():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    decision = p["orchestration"].refresh(context.context_id)

    assert decision.outcome == ACTIVATED
    assert decision.plan_id is not None
    assert decision.execution_id is not None
    assert decision.validation_id is not None
    assert p["context"].get(context.context_id).content == "v2 content"


def test_planning_failure():
    p = _pipeline()

    context = p["context"].create("notebook-1", "fact", "no provenance yet")
    before = p["context"].get(context.context_id)

    decision = p["orchestration"].refresh(context.context_id)

    assert decision.outcome == PLANNING_FAILED
    assert decision.plan_id is not None
    assert decision.execution_id is None
    after = p["context"].get(context.context_id)
    assert after.content == before.content
    assert after.updated_at == before.updated_at


def test_refresh_failure():
    p = _pipeline()

    artifact = p["artifact_store"].save(
        ResearchArtifact(
            session_id="session-1",
            object_id="paper-1",
            artifact_type=ResearchArtifactType.SUMMARY,
            content="artifact v1",
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
    # the artifact changes to a new, secret-laden version -- makes the
    # context stale, but the refresh itself cannot ever apply
    p["artifact_store"].save(
        dataclasses.replace(
            artifact, version=artifact.version + 1, content="api_key=sk-abcdefghijklmnopqrstuvwxyz"
        )
    )
    before = p["context"].get(context.context_id)

    decision = p["orchestration"].refresh(context.context_id)

    assert decision.outcome == REFRESH_FAILED
    assert decision.plan_id is not None
    assert decision.execution_id is not None
    assert decision.validation_id is None
    after = p["context"].get(context.context_id)
    assert after.content == before.content == "original safe content"
    assert after.updated_at == before.updated_at


def test_validation_failure_refuses_activation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)
    assert execution.status == "succeeded"

    # corrupt provenance after a genuine success, so Commit #12 finds a
    # blocking finding for an execution that otherwise looks fine
    del p["provenance"]._records_by_context[context.context_id]

    with pytest.raises(ActivationRefusedError):
        p["orchestration"].activate(execution.execution_id)


def test_activation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)

    decision = p["orchestration"].activate(execution.execution_id)

    assert decision.outcome == ACTIVATED
    assert decision.context_id == context.context_id
    assert decision.execution_id == execution.execution_id
    assert decision.validation_id is not None


def test_rollback_leaves_usable_previous_version():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)
    original_content = p["context"].get(context.context_id).content

    decision = p["orchestration"].refresh(context.context_id)
    assert decision.outcome == ACTIVATED
    assert p["context"].get(context.context_id).content == "v2 content"

    rolled_back = p["orchestration"].rollback(decision.execution_id)

    assert rolled_back.status == "rolled_back"
    restored = p["context"].get(context.context_id)
    assert restored.content == original_content
    assert p["orchestration"].status(decision.execution_id).status == "rolled_back"


def test_version_and_provenance_preservation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    version_history_before = p["version"].history(context.context_id)
    provenance_before = p["provenance"].sources(context.context_id)

    decision = p["orchestration"].refresh(context.context_id)
    assert decision.outcome == ACTIVATED

    version_history_after = p["version"].history(context.context_id)
    provenance_after = p["provenance"].sources(context.context_id)

    assert len(version_history_after) > len(version_history_before)
    assert [v.version for v in version_history_before] == [
        v.version for v in version_history_after[: len(version_history_before)]
    ]
    assert len(provenance_after) > len(provenance_before)
    assert provenance_after[: len(provenance_before)] == provenance_before


def test_deterministic_final_state():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    first = p["orchestration"].refresh(context.context_id)
    assert first.outcome == ACTIVATED

    # calling refresh() again on an already-activated, now-fresh context
    # converges to a stable no-op rather than refreshing again
    second = p["orchestration"].refresh(context.context_id)
    assert second.outcome == NOOP_FRESH
    assert p["context"].get(context.context_id).content == "v2 content"

    third = p["orchestration"].refresh(context.context_id)
    assert third.outcome == NOOP_FRESH
