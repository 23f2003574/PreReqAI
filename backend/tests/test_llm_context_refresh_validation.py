from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_refresh import LLMContextRefreshService
from backend.llm.context_refresh_execution import LLMContextRefreshExecutionService
from backend.llm.context_refresh_validation import (
    MALFORMED_CONTENT,
    MISSING_PROVENANCE,
    SOURCE_VERSION_MISMATCH,
    STALE_REFRESH,
    UNVERIFIABLE_FRESHNESS,
    LLMContextRefreshValidationService,
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
    validation_service = LLMContextRefreshValidationService(execution_service, freshness_service)
    return {
        "context": context_service,
        "version": version_service,
        "artifact_store": artifact_store,
        "provenance": provenance_service,
        "freshness": freshness_service,
        "refresh": refresh_service,
        "execution": execution_service,
        "validation": validation_service,
    }


def _refresh_context_version(p, scope_id="notebook-1"):
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

    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)
    return context, execution, v2


def test_valid_refresh():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    validation = p["validation"].validate(execution.execution_id)

    assert validation.execution_id == execution.execution_id
    assert validation.valid is True
    assert validation.findings == ()
    assert validation.validation_id is not None
    assert validation.checked_at is not None


def test_malformed_context():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    # bypass Commit #1's own write-time validation to simulate the stored
    # content having become malformed after the fact
    p["context"].store._contexts[context.context_id].content = ""

    findings = p["validation"].findings(execution.execution_id)

    codes = [f["code"] for f in findings]
    assert MALFORMED_CONTENT in codes
    assert p["validation"].validate(execution.execution_id).valid is False


def test_source_version_mismatch():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    # a valid-looking but wrong value: passes Commit #1's own validation,
    # but does not match what the pinned source/version actually holds
    p["context"].store._contexts[context.context_id].content = "not what the source says"

    findings = p["validation"].findings(execution.execution_id)
    codes = [f["code"] for f in findings]

    assert SOURCE_VERSION_MISMATCH in codes
    assert MALFORMED_CONTENT not in codes


def test_stale_refresh():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    # the source moves again right after the refresh completed
    p["context"].update(context.context_id, "v3 content")
    p["version"].snapshot(context.context_id)
    # ^ this call also updated `context`'s own content -- but the execution
    # under validation refreshed the context to v2, and nothing re-ran
    # plan()/execute() to catch up, so re-checking that execution's result
    # against the source must now report staleness
    p["context"].store._contexts[context.context_id].content = "v2 content"  # restore what was actually refreshed

    findings = p["validation"].findings(execution.execution_id)
    codes = [f["code"] for f in findings]

    assert STALE_REFRESH in codes
    assert p["validation"].validate(execution.execution_id).valid is False


def test_missing_provenance():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    del p["provenance"]._records_by_context[context.context_id]

    findings = p["validation"].findings(execution.execution_id)
    codes = [f["code"] for f in findings]

    assert MISSING_PROVENANCE in codes
    assert p["validation"].validate(execution.execution_id).valid is False


def test_blocking_finding():
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
    updated_artifact_store_entry = p["artifact_store"].save(
        ResearchArtifact(
            id=artifact.id,
            session_id=artifact.session_id,
            object_id=artifact.object_id,
            artifact_type=artifact.artifact_type,
            content="artifact v2",
            version=artifact.version + 1,
        )
    )
    plan = p["refresh"].plan(context.context_id)
    execution = p["execution"].execute(plan.plan_id)
    assert execution.status == "succeeded"

    # provenance now exists and is correct, but goes missing afterward --
    # which also makes freshness UNKNOWN (non-blocking) alongside it
    del p["provenance"]._records_by_context[context.context_id]

    all_findings = p["validation"].findings(execution.execution_id)
    blocking = p["validation"].blocking(execution.execution_id)

    assert any(f["code"] == MISSING_PROVENANCE for f in blocking)
    assert all(f["blocking"] for f in blocking)
    assert len(blocking) < len(all_findings)
    assert any(f["code"] == UNVERIFIABLE_FRESHNESS and not f["blocking"] for f in all_findings)


def test_existing_version_preservation():
    p = _pipeline()
    context, execution, v2 = _refresh_context_version(p)

    history_before = p["version"].history(context.context_id)
    context_before = p["context"].get(context.context_id)

    p["validation"].validate(execution.execution_id)
    p["validation"].findings(execution.execution_id)
    p["validation"].blocking(execution.execution_id)

    history_after = p["version"].history(context.context_id)
    context_after = p["context"].get(context.context_id)

    assert [v.version for v in history_after] == [v.version for v in history_before]
    assert context_after.content == context_before.content
    assert context_after.updated_at == context_before.updated_at
