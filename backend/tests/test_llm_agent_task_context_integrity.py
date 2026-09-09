import pytest

from backend.agent_policy_engine import DENY, LLMAgentPolicyService
from backend.agent_task_context_integrity import (
    ContextIntegrityResult,
    InvalidContextIntegrityError,
    LLMAgentTaskContextIntegrityService,
)
from backend.agent_task_context_packaging import AgentContextPackage
from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_injection import CONTEXT_ROLE
from backend.llm.context_provenance import LLMContextProvenance, LLMContextProvenanceService
from backend.llm.context_snapshot import LLMContextSnapshotService
from backend.llm.project_context import LLMProjectContextService


def _task(**overrides):
    task = {"task_id": "task-1", "agent_id": "agent-1", "scope_id": "scope-1", "objective": "do work", "inputs": {}}
    task.update(overrides)
    return task


def _package(task=None, constraints=None, context=None, memories=None, provenance=None, metadata=None):
    return AgentContextPackage(
        task=task if task is not None else _task(),
        constraints=constraints or [],
        context=context or [],
        memories=memories or [],
        provenance=provenance or [],
        metadata=metadata or {},
    )


def _message(context_id, content="hello world", context_type="fact", scope_id="scope-1", role=CONTEXT_ROLE):
    return {
        "role": role,
        "content": content,
        "metadata": {"context_id": context_id, "scope_id": scope_id, "context_type": context_type},
    }


def _provenance(context_id, source_type="project_context", source_id=None, excerpt="an excerpt"):
    return LLMContextProvenance(
        context_id=context_id, source_type=source_type, source_id=source_id or context_id, excerpt=excerpt
    )


def _service(**kwargs):
    return LLMAgentTaskContextIntegrityService(**kwargs)


# --- valid package passes ------------------------------------------------------------------


def test_valid_package_passes():
    context_id = "ctx-1"
    package = _package(
        context=[_message(context_id)],
        provenance=[_provenance(context_id)],
    )

    result = _service().validate(package, "agent-1", "scope-1")

    assert isinstance(result, ContextIntegrityResult)
    assert result.valid is True
    assert result.errors == []
    assert result.invalid_sources == []
    assert result.stale_sources == []
    assert result.provenance_issues == []


def test_valid_package_with_memories_passes():
    memory = {"memory_id": "mem-1", "scope_id": "scope-1", "content": "a proven strategy", "memory_type": "strategy"}
    package = _package(memories=[memory], provenance=[_provenance("mem-1", source_type="agent_memory")])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is True


# --- wrong scope/agent is rejected ----------------------------------------------------------


def test_wrong_agent_is_rejected():
    package = _package(task=_task(agent_id="agent-1"))

    result = _service().validate(package, "agent-2", "scope-1")

    assert result.valid is False
    assert any("agent-2" in error for error in result.errors)


def test_wrong_scope_is_rejected():
    package = _package(task=_task(scope_id="scope-1"))

    result = _service().validate(package, "agent-1", "scope-2")

    assert result.valid is False
    assert any("scope-2" in error for error in result.errors)


# --- missing provenance is detected -----------------------------------------------------------


def test_missing_provenance_is_detected():
    package = _package(context=[_message("ctx-1")], provenance=[])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert {"id": "ctx-1", "issue": "missing provenance"} in result.provenance_issues


def test_inconsistent_provenance_source_type_is_detected():
    bad_provenance = LLMContextProvenance(context_id="ctx-1", source_type="not-a-real-type", source_id="ctx-1", excerpt="x")
    package = _package(context=[_message("ctx-1")], provenance=[bad_provenance])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    issue_ids = {issue["id"] for issue in result.provenance_issues}
    assert "ctx-1" in issue_ids


def test_missing_memory_provenance_is_detected():
    memory = {"memory_id": "mem-1", "scope_id": "scope-1", "content": "x", "memory_type": "strategy"}
    package = _package(memories=[memory], provenance=[])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert {"id": "mem-1", "issue": "missing provenance"} in result.provenance_issues


# --- stale sources follow existing freshness rules ------------------------------------------


def test_stale_context_is_detected_via_existing_freshness_service():
    project_context_service = LLMProjectContextService()
    provenance_service = LLMContextProvenanceService(project_context_service)
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(project_context_service, provenance_service, snapshot_service)

    context = project_context_service.create("scope-1", "fact", "original content")
    recorded_provenance = provenance_service.attach(
        context.context_id,
        {"source_type": "project_context", "source_id": context.context_id, "excerpt": "original"},
    )
    project_context_service.update(context.context_id, "revised content, after provenance was recorded")

    package = _package(
        context=[_message(context.context_id)],
        provenance=[recorded_provenance],
    )

    result = _service(freshness_service=freshness_service).validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert context.context_id in result.stale_sources


def test_fresh_context_is_not_flagged_stale():
    project_context_service = LLMProjectContextService()
    provenance_service = LLMContextProvenanceService(project_context_service)
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(project_context_service, provenance_service, snapshot_service)

    context = project_context_service.create("scope-1", "fact", "original content")
    recorded_provenance = provenance_service.attach(
        context.context_id,
        {"source_type": "project_context", "source_id": context.context_id, "excerpt": "original"},
    )

    package = _package(context=[_message(context.context_id)], provenance=[recorded_provenance])

    result = _service(freshness_service=freshness_service).validate(package, "agent-1", "scope-1")

    assert result.valid is True
    assert context.context_id not in result.stale_sources


def test_no_freshness_service_never_flags_staleness():
    package = _package(context=[_message("ctx-1")], provenance=[_provenance("ctx-1")])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.stale_sources == []


# --- unauthorized sources are rejected ------------------------------------------------------


def test_unauthorized_context_is_rejected():
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-ctx", [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": "ctx-1"}}]
    )
    package = _package(context=[_message("ctx-1")], provenance=[_provenance("ctx-1")])

    result = _service(policy_service=policy_service).validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert "ctx-1" in result.invalid_sources


def test_no_policy_service_never_flags_unauthorized():
    package = _package(context=[_message("ctx-1")], provenance=[_provenance("ctx-1")])

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.invalid_sources == []


def test_secret_content_is_rejected():
    package = _package(
        context=[_message("ctx-1", content="password: supersecretvalue123")],
        provenance=[_provenance("ctx-1")],
    )

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert "ctx-1" in result.invalid_sources


# --- mixed valid/invalid sources are reported correctly ---------------------------------------


def test_mixed_valid_and_invalid_sources_are_reported_independently():
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-bad", [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": "ctx-bad"}}]
    )
    package = _package(
        context=[_message("ctx-good"), _message("ctx-bad")],
        provenance=[_provenance("ctx-good")],  # ctx-bad has no provenance at all
    )

    result = _service(policy_service=policy_service).validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert "ctx-bad" in result.invalid_sources
    assert "ctx-good" not in result.invalid_sources
    assert {"id": "ctx-bad", "issue": "missing provenance"} in result.provenance_issues
    assert all(issue["id"] != "ctx-good" for issue in result.provenance_issues)


def test_malformed_message_shape_is_reported():
    package = _package(context=[{"role": CONTEXT_ROLE}])  # missing "content"

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert any("malformed" in error for error in result.errors)


def test_mandatory_task_data_missing_is_reported():
    package = _package(task=_task(objective=""))

    result = _service().validate(package, "agent-1", "scope-1")

    assert result.valid is False
    assert any("objective" in error for error in result.errors)


# --- integrity validation performs no mutation --------------------------------------------------


def test_validation_is_side_effect_free():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "content")

    package = _package(context=[_message(context.context_id)], provenance=[_provenance(context.context_id)])
    original_package = package

    _service().validate(package, "agent-1", "scope-1")

    assert package == original_package
    assert project_context_service.get(context.context_id) == context


def test_validation_is_deterministic():
    package = _package(context=[_message("ctx-1")], provenance=[_provenance("ctx-1")])
    service = _service()

    first = service.validate(package, "agent-1", "scope-1")
    second = service.validate(package, "agent-1", "scope-1")

    assert first == second


# --- invalid input is rejected ----------------------------------------------------------------


def test_invalid_package_type_rejected():
    with pytest.raises(InvalidContextIntegrityError):
        _service().validate("not-a-package", "agent-1", "scope-1")


def test_invalid_identifiers_rejected():
    package = _package()

    with pytest.raises(InvalidContextIntegrityError):
        _service().validate(package, "", "scope-1")
    with pytest.raises(InvalidContextIntegrityError):
        _service().validate(package, "agent-1", "")
