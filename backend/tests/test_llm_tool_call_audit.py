import dataclasses

import pytest

from backend.llm.tool_audit import (
    BrokenLifecycleLinkError,
    DuplicateAuditPlanError,
    LLMToolAudit,
    LLMToolAuditService,
    PLANNED,
    UnknownAuditError,
)
from backend.llm.tool_execution import (
    DENIED as EXECUTION_DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
)
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    AUTHORIZED,
    DENIED,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tools import LLMToolRegistryService

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string"},
        "api_key": {"type": "string"},
    },
    "required": ["analysis_id"],
}

SUMMARIES = {"analysis-1": {"cell_count": 3, "code_cell_count": 2}}


def summarize(analysis_id, api_key=None):
    return SUMMARIES[analysis_id]


def build(allow=True):
    registry = LLMToolRegistryService()
    registry.register(
        "summarize_notebook_analysis", "Summarize a notebook analysis.", SUMMARIZE_SCHEMA
    )
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    if allow:
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="allow-1",
                tool_name="summarize_notebook_analysis",
                subject=ANY_SUBJECT,
                allowed=True,
            )
        )
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", summarize)
    return registry, invocation, permissions, execution, LLMToolAuditService()


def plan_for(invocation, **arguments):
    return invocation.plan(
        {
            "name": "summarize_notebook_analysis",
            "arguments": arguments or {"analysis_id": "analysis-1"},
            "rationale": "The user asked how big the analysis is.",
        }
    )


# ---------------------------------------------------------------------------
# lifecycle linkage
# ---------------------------------------------------------------------------


def test_lifecycle_linkage_request_plan_execution():
    _, invocation, permissions, execution_service, audit = build()
    plan = plan_for(invocation)

    started = audit.start(plan, "conversation-1", subject="user:ada")
    assert started.status == PLANNED
    assert started.request_id == "conversation-1"
    assert started.plan_id == plan.plan_id
    assert started.execution_id is None
    assert started.tool_name == "summarize_notebook_analysis"
    assert started.subject == "user:ada"
    assert started.created_at is not None

    authorization = permissions.authorize(plan, "user:ada")
    audit.record_authorization(plan.plan_id, authorization)

    record = execution_service.execute(plan, "user:ada")
    recorded = audit.record_execution(record)

    assert recorded.execution_id == record.execution_id
    assert recorded.plan_id == plan.plan_id
    assert recorded.request_id == "conversation-1"
    assert recorded.status == SUCCEEDED

    final = audit.complete(record.execution_id, SUCCEEDED)
    assert final.completed_at is not None

    # The whole chain is reachable from any of the three identifiers.
    assert audit.get(record.execution_id) == final
    assert [a.plan_id for a in audit.history("conversation-1")] == [plan.plan_id] * 4
    assert len(audit.trail(plan.plan_id)) == 4


def test_an_execution_for_an_unstarted_plan_is_refused():
    _, invocation, _, execution_service, audit = build()
    plan = plan_for(invocation)
    record = execution_service.execute(plan, "user:ada")

    with pytest.raises(BrokenLifecycleLinkError, match="no audit trail"):
        audit.record_execution(record)


def test_an_execution_cannot_be_relinked_to_another_plan():
    _, invocation, _, execution_service, audit = build()
    first, second = plan_for(invocation), plan_for(invocation, analysis_id="analysis-2")
    audit.start(first, "conversation-1", subject="user:ada")
    audit.start(second, "conversation-1", subject="user:ada")
    record = execution_service.execute(first, "user:ada")
    audit.record_execution(record)

    relinked = dataclasses.replace(record, plan_id=second.plan_id)
    with pytest.raises(BrokenLifecycleLinkError, match="already recorded"):
        audit.record_execution(relinked)


def test_duplicate_start_for_one_plan_is_refused():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    with pytest.raises(DuplicateAuditPlanError):
        audit.start(plan, "conversation-1", subject="user:ada")


# ---------------------------------------------------------------------------
# authorization recording
# ---------------------------------------------------------------------------


def test_authorization_outcome_is_recorded():
    _, invocation, permissions, _, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    entry = audit.record_authorization(plan.plan_id, permissions.authorize(plan, "user:ada"))

    assert entry.status == AUTHORIZED
    assert entry.authorization == AUTHORIZED
    assert entry.authorization_policy_id == "allow-1"
    assert "allows subject" in entry.reason


def test_a_denial_is_recorded_and_stays_auditable():
    _, invocation, permissions, _, audit = build(allow=False)
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    entry = audit.record_authorization(plan.plan_id, permissions.authorize(plan, "user:ada"))

    assert entry.status == DENIED
    assert entry.authorization == DENIED
    assert entry.authorization_policy_id is None
    assert "denied by default" in entry.reason
    assert audit.trail(plan.plan_id)[-1] == entry


def test_authorization_can_be_passed_at_start():
    _, invocation, permissions, _, audit = build()
    plan = plan_for(invocation)

    entry = audit.start(
        plan,
        "conversation-1",
        subject="user:ada",
        authorization=permissions.authorize(plan, "user:ada"),
    )

    assert entry.authorization == AUTHORIZED
    # Still two snapshots: the trail is append-only, not overwritten.
    assert [a.status for a in audit.trail(plan.plan_id)] == [PLANNED, AUTHORIZED]


def test_record_authorization_requires_a_real_authorization():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    with pytest.raises(TypeError):
        audit.record_authorization(plan.plan_id, {"allowed": True})


# ---------------------------------------------------------------------------
# success / failure states
# ---------------------------------------------------------------------------


def test_a_failed_invocation_remains_auditable():
    _, invocation, _, execution_service, audit = build()
    plan = plan_for(invocation, analysis_id="analysis-missing")
    audit.start(plan, "conversation-1", subject="user:ada")

    record = execution_service.execute(plan, "user:ada")
    assert record.status == FAILED

    entry = audit.record_execution(record)

    assert entry.status == FAILED
    assert "KeyError" in entry.reason
    assert audit.get(record.execution_id).status == FAILED

    final = audit.complete(record.execution_id, FAILED)
    assert final.status == FAILED
    assert final.completed_at is not None


def test_a_denied_execution_is_recorded():
    _, invocation, _, execution_service, audit = build(allow=False)
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    record = execution_service.execute(plan, "user:ada")
    entry = audit.record_execution(record)

    assert record.status == EXECUTION_DENIED
    assert entry.status == EXECUTION_DENIED
    assert "denied by default" in entry.reason


def test_a_rejected_execution_is_recorded():
    registry, invocation, _, execution_service, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")
    registry.disable("summarize_notebook_analysis")

    record = execution_service.execute(plan, "user:ada")
    entry = audit.record_execution(record)

    assert record.status == REJECTED
    assert entry.status == REJECTED
    assert "disabled" in entry.reason


def test_complete_requires_a_known_execution_and_a_known_status():
    _, invocation, _, execution_service, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")
    record = execution_service.execute(plan, "user:ada")
    audit.record_execution(record)

    with pytest.raises(UnknownAuditError):
        audit.complete("does-not-exist", SUCCEEDED)

    with pytest.raises(ValueError, match="not one of"):
        audit.complete(record.execution_id, "MAYBE")


# ---------------------------------------------------------------------------
# history lookup
# ---------------------------------------------------------------------------


def test_history_lookup_spans_every_plan_of_one_conversation():
    _, invocation, permissions, execution_service, audit = build()
    first = plan_for(invocation)
    second = plan_for(invocation, analysis_id="analysis-1", api_key="x")

    audit.start(first, "conversation-1", subject="user:ada")
    audit.record_authorization(first.plan_id, permissions.authorize(first, "user:ada"))
    audit.record_execution(execution_service.execute(first, "user:ada"))

    audit.start(second, "conversation-1", subject="user:ada")
    audit.start(plan_for(invocation, analysis_id="analysis-2"), "conversation-2", "user:grace")

    history = audit.history("conversation-1")

    assert [a.plan_id for a in history] == [first.plan_id] * 3 + [second.plan_id]
    assert [a.status for a in history] == [PLANNED, AUTHORIZED, SUCCEEDED, PLANNED]
    assert [a.plan_id for a in audit.history("conversation-2")] != [first.plan_id]

    with pytest.raises(UnknownAuditError):
        audit.history("conversation-does-not-exist")


def test_unknown_lookups_raise():
    _, _, _, _, audit = build()

    for method in (audit.get, audit.history, audit.trail):
        with pytest.raises(UnknownAuditError):
            method("does-not-exist")


# ---------------------------------------------------------------------------
# immutability
# ---------------------------------------------------------------------------


def test_records_are_immutable_and_append_only():
    _, invocation, permissions, execution_service, audit = build()
    plan = plan_for(invocation)
    started = audit.start(plan, "conversation-1", subject="user:ada")
    snapshot = dataclasses.asdict(started)

    audit.record_authorization(plan.plan_id, permissions.authorize(plan, "user:ada"))
    record = execution_service.execute(plan, "user:ada")
    audit.record_execution(record)
    audit.complete(record.execution_id, SUCCEEDED)

    # The first snapshot is untouched by everything that followed it.
    assert dataclasses.asdict(audit.trail(plan.plan_id)[0]) == snapshot
    assert audit.trail(plan.plan_id)[0].status == PLANNED
    assert audit.trail(plan.plan_id)[0].execution_id is None

    # Each event appended, with its own audit_id.
    trail = audit.trail(plan.plan_id)
    assert len(trail) == 4
    assert len({a.audit_id for a in trail}) == 4

    with pytest.raises(dataclasses.FrozenInstanceError):
        trail[0].status = SUCCEEDED


def test_returned_collections_do_not_expose_internal_state():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    audit.history("conversation-1").append("tampered")
    audit.trail(plan.plan_id).append("tampered")

    assert len(audit.history("conversation-1")) == 1
    assert len(audit.trail(plan.plan_id)) == 1


# ---------------------------------------------------------------------------
# secret exclusion
# ---------------------------------------------------------------------------


def test_tool_arguments_are_never_stored():
    """Arguments can carry credentials and are not needed to reconstruct who
    asked for what -- the record has no field for them at all."""
    _, invocation, _, execution_service, audit = build()
    plan = plan_for(
        invocation, analysis_id="analysis-1", api_key="sk-abcdefghijklmnopqrst"
    )
    audit.start(plan, "conversation-1", subject="user:ada")
    record = execution_service.execute(plan, "user:ada")
    entry = audit.record_execution(record)

    assert not hasattr(entry, "arguments")
    assert not hasattr(entry, "output")
    assert not hasattr(entry, "result")

    stored = repr(dataclasses.asdict(entry))
    assert "sk-abcdefghijklmnopqrst" not in stored
    assert "api_key" not in stored


@pytest.mark.parametrize(
    "subject",
    [
        "sk-abcdefghijklmnopqrst",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "token=hunter2-supersecret",
    ],
)
def test_a_credential_shaped_subject_is_redacted(subject):
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)

    entry = audit.start(plan, "conversation-1", subject=subject)

    assert entry.subject == "[REDACTED]"


def test_a_collection_subject_is_normalized_and_redacted():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)

    entry = audit.start(
        plan, "conversation-1", subject=["role:maintainer", "sk-abcdefghijklmnopqrst"]
    )

    assert entry.subject == "[REDACTED],role:maintainer"


def test_a_credential_shaped_failure_reason_is_redacted():
    _, invocation, _, execution_service, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    def leaky(analysis_id, api_key=None):
        raise RuntimeError("upstream rejected api_key=sk-abcdefghijklmnop")

    execution_service.bind("summarize_notebook_analysis", leaky)
    entry = audit.record_execution(execution_service.execute(plan, "user:ada"))

    assert entry.status == FAILED
    assert "sk-" not in entry.reason


# ---------------------------------------------------------------------------
# no execution
# ---------------------------------------------------------------------------


def test_the_audit_service_executes_nothing():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)

    for attr in ("invoke", "call", "execute", "run", "dispatch", "bind"):
        assert not hasattr(audit, attr)

    before = dataclasses.asdict(plan)
    audit.start(plan, "conversation-1", subject="user:ada")
    assert dataclasses.asdict(plan) == before


def test_start_rejects_a_non_plan_and_a_missing_request_id():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)

    with pytest.raises(TypeError):
        audit.start({"plan_id": "p-1"}, "conversation-1")

    with pytest.raises(ValueError):
        audit.start(plan, "")


def test_record_execution_rejects_a_non_execution():
    _, invocation, _, _, audit = build()
    plan = plan_for(invocation)
    audit.start(plan, "conversation-1", subject="user:ada")

    with pytest.raises(TypeError):
        audit.record_execution({"execution_id": "e-1", "plan_id": plan.plan_id})


def test_audit_model_is_constructible_standalone():
    """The record is a plain frozen value object, like the codebase's others."""
    audit = LLMToolAudit(
        audit_id="audit-1",
        request_id="conversation-1",
        plan_id="plan-1",
        execution_id=None,
        tool_name="summarize_notebook_analysis",
        subject="user:ada",
        status=PLANNED,
    )

    assert audit.authorization is None
    assert audit.completed_at is None
