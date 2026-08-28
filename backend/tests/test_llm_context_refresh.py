import dataclasses

import pytest

from backend.llm.context_freshness import STALE, LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_refresh import (
    ACTIONABLE,
    UNRESOLVABLE,
    InvalidRefreshPlanError,
    LLMContextRefreshPlan,
    LLMContextRefreshService,
    NothingToRefreshError,
    UnknownRefreshPlanError,
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
    return {
        "context": context_service,
        "version": version_service,
        "artifact_store": artifact_store,
        "provenance": provenance_service,
        "freshness": freshness_service,
        "refresh": refresh_service,
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


def test_stale_source_detection():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)

    assert len(plan.stale_sources) == 1
    source = plan.stale_sources[0]
    assert source["source_type"] == "context_version"
    assert source["source_id"] == context.context_id
    assert source["source_version"] == v1.version
    assert source["status"] == STALE


def test_refresh_plan_generation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)

    assert isinstance(plan, LLMContextRefreshPlan)
    assert plan.context_id == context.context_id
    assert plan.plan_id is not None
    assert plan.reason
    assert plan.status == ACTIONABLE
    assert len(plan.refresh_actions) == 1

    action = plan.refresh_actions[0]
    assert action["source_type"] == "context_version"
    assert action["source_id"] == context.context_id
    assert action["current_version"] == v2.version
    assert action["current_content"] == "v2 content"

    # a fresh context has nothing to plan
    fresh_context, _, _ = None, None, None
    fresh_context = p["context"].create("notebook-1", "fact", "already fresh")
    v = p["version"].snapshot(fresh_context.context_id)
    p["provenance"].attach(
        fresh_context.context_id,
        {
            "source_type": "context_version",
            "source_id": fresh_context.context_id,
            "source_version": v.version,
            "excerpt": "fresh",
        },
    )
    with pytest.raises(NothingToRefreshError):
        p["refresh"].plan(fresh_context.context_id)


def test_unknown_source_handling():
    p = _pipeline()

    context = p["context"].create("notebook-1", "fact", "no provenance yet")
    plan = p["refresh"].plan(context.context_id)

    assert plan.status == UNRESOLVABLE
    assert plan.refresh_actions == ()
    assert plan.stale_sources[0]["source_type"] is None

    external_context = p["context"].create("notebook-1", "fact", "external sourced")
    p["provenance"].attach(
        external_context.context_id,
        {"source_type": "external", "source_id": "notebook-1#cell-1", "excerpt": "cell content"},
    )
    external_plan = p["refresh"].plan(external_context.context_id)

    assert external_plan.status == UNRESOLVABLE
    assert external_plan.refresh_actions == ()
    assert external_plan.stale_sources[0]["source_type"] == "external"


def test_invalid_artifact_rejection():
    p = _pipeline()

    artifact = p["artifact_store"].save(
        ResearchArtifact(
            session_id="session-1",
            object_id="paper-1",
            artifact_type=ResearchArtifactType.SUMMARY,
            content="artifact v1",
        )
    )
    context = p["context"].create("notebook-1", "summary", "artifact-derived summary")
    p["provenance"].attach(
        context.context_id,
        {
            "source_type": "research_artifact",
            "source_id": artifact.id,
            "source_version": artifact.version,
            "excerpt": "from artifact v1",
        },
    )
    updated_artifact = dataclasses.replace(artifact, version=artifact.version + 1, content="v2")
    p["artifact_store"].save(updated_artifact)

    plan = p["refresh"].plan(context.context_id)
    assert p["refresh"].validate(plan.plan_id) is True

    # the artifact this plan's action points at is now gone entirely
    p["artifact_store"].delete(artifact.id)

    with pytest.raises(InvalidRefreshPlanError):
        p["refresh"].validate(plan.plan_id)

    with pytest.raises(UnknownRefreshPlanError):
        p["refresh"].validate("not-a-real-plan-id")


def test_provenance_preservation():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)

    original_provenance = p["provenance"].get(context.context_id)
    assert plan.stale_sources[0]["source_type"] == original_provenance.source_type
    assert plan.stale_sources[0]["source_id"] == original_provenance.source_id
    assert plan.stale_sources[0]["source_version"] == original_provenance.source_version

    # planning never touches the provenance record itself
    after = p["provenance"].get(context.context_id)
    assert after == original_provenance
    assert len(p["provenance"].sources(context.context_id)) == 1


def test_preview():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)
    before = p["context"].get(context.context_id)

    preview = p["refresh"].preview(plan.plan_id)

    assert len(preview) == 1
    entry = preview[0]
    assert entry["context_id"] == context.context_id
    assert entry["current_content"] == "v2 content"  # the context's current stored content
    assert entry["proposed_content"] == "v2 content"  # what the latest version already holds
    assert entry["current_version"] == v2.version

    # preview is read-only: nothing about the stored context changed
    after = p["context"].get(context.context_id)
    assert after.content == before.content
    assert after.updated_at == before.updated_at


def test_source_immutability():
    p = _pipeline()
    context, v1, v2 = _make_stale_context_version(p)

    plan = p["refresh"].plan(context.context_id)

    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.status = ACTIONABLE

    fetched = p["refresh"].get(plan.plan_id)
    fetched.refresh_actions[0]["current_content"] = "tampered"
    fetched.stale_sources[0]["reason"] = "tampered"

    refetched = p["refresh"].get(plan.plan_id)
    assert refetched.refresh_actions[0]["current_content"] == "v2 content"
    assert refetched.stale_sources[0]["reason"] == plan.reason
