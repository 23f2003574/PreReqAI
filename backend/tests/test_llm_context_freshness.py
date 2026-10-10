import dataclasses

from backend.llm import LLMRequest
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_freshness import FRESH, STALE, UNKNOWN, LLMContextFreshnessService
from backend.llm.context_injection import LLMContextInjectionService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_retrieval import LLMContextRetrievalService
from backend.llm.context_selection import LLMContextSelectionService
from backend.llm.context_snapshot import LLMContextSnapshotService
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
    retrieval_service = LLMContextRetrievalService(context_service)
    selection_service = LLMContextSelectionService()
    compaction_service = LLMContextCompactionService()
    injection_service = LLMContextInjectionService(
        retrieval_service, selection_service, compaction_service, provenance_service
    )
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(
        context_service, provenance_service, snapshot_service
    )
    return {
        "context": context_service,
        "version": version_service,
        "artifact_store": artifact_store,
        "provenance": provenance_service,
        "injection": injection_service,
        "snapshot": snapshot_service,
        "freshness": freshness_service,
    }


def test_fresh_context():
    p = _pipeline()

    context = p["context"].create("notebook-1", "summary", "v1 content")
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

    result = p["freshness"].check(context.context_id)

    assert result.status == FRESH
    assert result.subject_id == context.context_id
    assert p["freshness"].stale(context.context_id) is False


def test_changed_source_marks_context_version_stale():
    p = _pipeline()

    context = p["context"].create("notebook-1", "summary", "v1 content")
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
    assert p["freshness"].check(context.context_id).status == FRESH

    # the underlying context changes and gets a new version after provenance
    # was captured
    p["context"].update(context.context_id, "v2 content")
    p["version"].snapshot(context.context_id)

    result = p["freshness"].check(context.context_id)
    assert result.status == STALE
    assert p["freshness"].stale(context.context_id) is True


def test_stale_research_artifact_version():
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
    assert p["freshness"].check(context.context_id).status == FRESH

    # the artifact is updated to a new version after provenance was captured
    updated_artifact = dataclasses.replace(artifact, version=artifact.version + 1, content="artifact v2")
    p["artifact_store"].save(updated_artifact)

    result = p["freshness"].check(context.context_id)
    assert result.status == STALE
    assert str(artifact.version) in result.reason
    assert str(updated_artifact.version) in result.reason


def test_unknown_provenance():
    p = _pipeline()

    context = p["context"].create("notebook-1", "fact", "no provenance yet")

    result = p["freshness"].check(context.context_id)
    assert result.status == UNKNOWN
    assert p["freshness"].stale(context.context_id) is True  # never silently fresh

    # a source_type nothing in the repo can verify is unknown too, not fresh
    p["provenance"].attach(
        context.context_id,
        {"source_type": "external", "source_id": "notebook-1#cell-1", "excerpt": "cell content"},
    )
    result_external = p["freshness"].check(context.context_id)
    assert result_external.status == UNKNOWN
    assert p["freshness"].stale(context.context_id) is True


def test_snapshot_freshness():
    p = _pipeline()

    fresh_context = p["context"].create("notebook-1", "summary", "fresh content")
    v1 = p["version"].snapshot(fresh_context.context_id)
    p["provenance"].attach(
        fresh_context.context_id,
        {
            "source_type": "context_version",
            "source_id": fresh_context.context_id,
            "source_version": v1.version,
            "excerpt": "fresh",
        },
    )

    stale_context = p["context"].create("notebook-1", "summary", "stale content v1")
    v1b = p["version"].snapshot(stale_context.context_id)
    p["provenance"].attach(
        stale_context.context_id,
        {
            "source_type": "context_version",
            "source_id": stale_context.context_id,
            "source_version": v1b.version,
            "excerpt": "captured v1",
        },
    )
    p["context"].update(stale_context.context_id, "stale content v2")
    p["version"].snapshot(stale_context.context_id)

    prepared = p["injection"].prepare("notebook-1", "content", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = p["injection"].inject(request, prepared)
    snapshot = p["snapshot"].create("req-1", injected)

    result = p["freshness"].check_snapshot(snapshot.snapshot_id)
    assert result.status == STALE
    assert result.subject_id == snapshot.snapshot_id

    # an all-fresh snapshot reports fresh
    fresh_only = p["injection"].inject(
        LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}]),
        [fresh_context],
    )
    fresh_snapshot = p["snapshot"].create("req-2", fresh_only)
    assert p["freshness"].check_snapshot(fresh_snapshot.snapshot_id).status == FRESH

    # a snapshot with no context items is trivially fresh
    empty_snapshot = p["snapshot"].create(
        "req-3", LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    )
    assert p["freshness"].check_snapshot(empty_snapshot.snapshot_id).status == FRESH


def test_refresh_candidate_detection():
    p = _pipeline()

    context = p["context"].create("notebook-1", "summary", "v1 content")
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

    # fresh: nothing to refresh
    assert p["freshness"].refresh_candidates(context.context_id) == []

    p["context"].update(context.context_id, "v2 content")
    v2 = p["version"].snapshot(context.context_id)

    candidates = p["freshness"].refresh_candidates(context.context_id)
    assert len(candidates) == 1
    assert candidates[0]["source_type"] == "context_version"
    assert candidates[0]["source_id"] == context.context_id
    assert candidates[0]["current_version"] == v2.version
    assert candidates[0]["current_content"] == "v2 content"

    # read-only: the context itself is untouched by asking for candidates
    assert p["context"].get(context.context_id).content == "v2 content"


def test_scope_isolation():
    p = _pipeline()

    stale_context = p["context"].create("scope-a", "summary", "v1 content")
    v1 = p["version"].snapshot(stale_context.context_id)
    p["provenance"].attach(
        stale_context.context_id,
        {
            "source_type": "context_version",
            "source_id": stale_context.context_id,
            "source_version": v1.version,
            "excerpt": "captured v1",
        },
    )
    p["context"].update(stale_context.context_id, "v2 content")
    p["version"].snapshot(stale_context.context_id)

    fresh_context = p["context"].create("scope-b", "summary", "unrelated content")
    v1b = p["version"].snapshot(fresh_context.context_id)
    p["provenance"].attach(
        fresh_context.context_id,
        {
            "source_type": "context_version",
            "source_id": fresh_context.context_id,
            "source_version": v1b.version,
            "excerpt": "captured v1",
        },
    )

    assert p["freshness"].check(stale_context.context_id).status == STALE
    assert p["freshness"].check(fresh_context.context_id).status == FRESH
