import json
import threading

import pytest

from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_execution import (
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
)
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tools import LLMToolRegistryService

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string"},
        "verbose": {"type": "boolean"},
    },
    "required": ["analysis_id"],
}

SUMMARIES = {"analysis-1": {"cell_count": 3}, "analysis-2": {"cell_count": 9}}


class CountingTool:
    """A real handler that records how many times it actually ran."""

    def __init__(self, fail_times=0):
        self.calls = 0
        self.fail_times = fail_times

    def __call__(self, analysis_id, verbose=False):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient upstream failure")
        return SUMMARIES[analysis_id]


def build(fail_times=0, allow=True, with_permissions=True, with_audit=False):
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
    tool = CountingTool(fail_times=fail_times)
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", tool)

    audit = LLMToolAuditService() if with_audit else None
    idempotency = LLMToolIdempotencyService(
        execution, permissions if with_permissions else None, audit
    )
    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "execution": execution,
        "idempotency": idempotency,
        "audit": audit,
        "tool": tool,
    }


def plan_for(stack, **arguments):
    return stack["invocation"].plan(
        {
            "name": "summarize_notebook_analysis",
            "arguments": arguments or {"analysis_id": "analysis-1"},
        }
    )


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------


def test_key_follows_the_projects_hashing_convention():
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)

    key = idempotency.key(plan, "user:ada")

    # Same shape as LLMResponseCacheService.compute_key: scope, then digest.
    tool_name, digest = key.split(":", 1)
    assert tool_name == "summarize_notebook_analysis"
    assert len(digest) == 64  # sha256 hexdigest, as LLMResponseCacheService uses


def test_a_subject_containing_the_separator_cannot_collide():
    """A subject like "user:ada" contains the key separator, so tool name and
    subject are hashed, not merely concatenated into the prefix."""
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)

    assert idempotency.key(plan, "user:ada") != idempotency.key(plan, "user")
    assert idempotency.key(plan, "a:b") != idempotency.key(plan, "a")
    assert idempotency.key(plan, ["a", "b"]) != idempotency.key(plan, "a,b:")


def test_the_same_logical_call_keys_the_same_however_it_is_expressed():
    """A plan, the raw dict, and its JSON text are the same logical call."""
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack, analysis_id="analysis-1", verbose=True)
    raw = {
        "name": "summarize_notebook_analysis",
        "arguments": {"verbose": True, "analysis_id": "analysis-1"},
    }

    assert idempotency.key(plan, "user:ada") == idempotency.key(raw, "user:ada")
    assert idempotency.key(json.dumps(raw), "user:ada") == idempotency.key(plan, "user:ada")


def test_different_arguments_give_different_keys():
    stack = build()
    idempotency = stack["idempotency"]

    first = idempotency.key(plan_for(stack, analysis_id="analysis-1"), "user:ada")
    second = idempotency.key(plan_for(stack, analysis_id="analysis-2"), "user:ada")
    extra = idempotency.key(
        plan_for(stack, analysis_id="analysis-1", verbose=True), "user:ada"
    )

    assert len({first, second, extra}) == 3


def test_different_subjects_give_different_keys():
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)

    assert idempotency.key(plan, "user:ada") != idempotency.key(plan, "user:grace")
    assert idempotency.key(plan, ["role:a", "role:b"]) == idempotency.key(
        plan, ["role:b", "role:a"]
    )


# ---------------------------------------------------------------------------
# duplicate calls / result reuse
# ---------------------------------------------------------------------------


def test_duplicate_call_runs_the_tool_once():
    stack = build()
    idempotency, tool = stack["idempotency"], stack["tool"]

    first = idempotency.execute_once(plan_for(stack), "user:ada")
    second = idempotency.execute_once(plan_for(stack), "user:ada")

    assert tool.calls == 1
    assert first.status == SUCCEEDED
    assert second is first
    assert second.execution_id == first.execution_id
    assert second.result == {"cell_count": 3}


def test_result_reuse_is_observable():
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)
    key = idempotency.key(plan, "user:ada")

    assert idempotency.existing(key) is None
    assert idempotency.reuse_count(key) == 0

    executed = idempotency.execute_once(plan, "user:ada")
    assert idempotency.existing(key) is executed
    assert idempotency.reuse_count(key) == 0

    idempotency.execute_once(plan_for(stack), "user:ada")
    idempotency.execute_once(plan_for(stack), "user:ada")
    assert idempotency.reuse_count(key) == 2
    assert stack["tool"].calls == 1


def test_a_different_plan_id_for_the_same_logical_call_still_reuses():
    """Idempotency is about the call, not the plan record."""
    stack = build()
    first_plan, second_plan = plan_for(stack), plan_for(stack)
    assert first_plan.plan_id != second_plan.plan_id

    first = stack["idempotency"].execute_once(first_plan, "user:ada")
    second = stack["idempotency"].execute_once(second_plan, "user:ada")

    assert second is first
    assert stack["tool"].calls == 1


def test_different_arguments_execute_separately():
    stack = build()
    idempotency, tool = stack["idempotency"], stack["tool"]

    first = idempotency.execute_once(plan_for(stack, analysis_id="analysis-1"), "user:ada")
    second = idempotency.execute_once(plan_for(stack, analysis_id="analysis-2"), "user:ada")

    assert tool.calls == 2
    assert first.execution_id != second.execution_id
    assert first.result == {"cell_count": 3}
    assert second.result == {"cell_count": 9}


def test_different_subjects_execute_separately():
    stack = build()
    idempotency, tool = stack["idempotency"], stack["tool"]

    first = idempotency.execute_once(plan_for(stack), "user:ada")
    second = idempotency.execute_once(plan_for(stack), "user:grace")

    assert tool.calls == 2
    assert first.execution_id != second.execution_id


# ---------------------------------------------------------------------------
# retry semantics
# ---------------------------------------------------------------------------


def test_retry_after_failure_re_executes():
    """A failure is never memoized -- the same rule LLMResponseCacheService
    applies to unsuccessful responses -- so a retry genuinely runs again."""
    stack = build(fail_times=1)
    idempotency, tool = stack["idempotency"], stack["tool"]
    key = idempotency.key(plan_for(stack), "user:ada")

    failed = idempotency.execute_once(plan_for(stack), "user:ada")
    assert failed.status == FAILED
    assert idempotency.existing(key) is None

    retried = idempotency.execute_once(plan_for(stack), "user:ada")

    assert retried.status == SUCCEEDED
    assert tool.calls == 2
    assert idempotency.existing(key) is retried

    # Once it has succeeded, it is remembered like any other success.
    idempotency.execute_once(plan_for(stack), "user:ada")
    assert tool.calls == 2


def test_a_denied_execution_is_not_memoized():
    stack = build(allow=False)
    idempotency = stack["idempotency"]
    key = idempotency.key(plan_for(stack), "user:ada")

    denied = idempotency.execute_once(plan_for(stack), "user:ada")

    assert denied.status == DENIED
    assert idempotency.existing(key) is None
    assert stack["tool"].calls == 0


def test_a_rejected_execution_is_not_memoized():
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)
    stack["registry"].disable("summarize_notebook_analysis")

    rejected = idempotency.execute_once(plan, "user:ada")

    assert rejected.status == REJECTED
    assert idempotency.existing(idempotency.key(plan, "user:ada")) is None


def test_forget_makes_the_next_call_execute_again():
    stack = build()
    idempotency = stack["idempotency"]
    plan = plan_for(stack)
    idempotency.execute_once(plan, "user:ada")
    key = idempotency.key(plan, "user:ada")

    assert idempotency.forget(key) is True
    assert idempotency.forget(key) is False

    idempotency.execute_once(plan_for(stack), "user:ada")
    assert stack["tool"].calls == 2


# ---------------------------------------------------------------------------
# validation and permissions are never bypassed
# ---------------------------------------------------------------------------


def test_a_reused_result_is_re_authorized():
    """Reuse must not outlive the permission that produced it."""
    stack = build()
    idempotency, permissions = stack["idempotency"], stack["permissions"]
    first = idempotency.execute_once(plan_for(stack), "user:ada")
    assert first.status == SUCCEEDED

    permissions.register(
        LLMToolPermissionPolicy(
            policy_id="deny-ada",
            tool_name="summarize_notebook_analysis",
            subject="user:ada",
            allowed=False,
        )
    )

    after = idempotency.execute_once(plan_for(stack), "user:ada")

    assert after.status == DENIED
    assert after.execution_id != first.execution_id
    assert stack["tool"].calls == 1  # the tool did not run again either
    # ...and another subject, still permitted, is unaffected.
    assert idempotency.execute_once(plan_for(stack), "user:grace").status == SUCCEEDED


def test_a_disabled_tool_is_not_served_from_memory():
    stack = build()
    idempotency = stack["idempotency"]
    assert idempotency.execute_once(plan_for(stack), "user:ada").status == SUCCEEDED

    stack["registry"].disable("summarize_notebook_analysis")

    after = idempotency.execute_once(plan_for(stack), "user:ada")
    assert after.status == REJECTED


def test_an_invalid_plan_is_never_executed_or_memoized():
    stack = build()
    idempotency = stack["idempotency"]
    bad = stack["invocation"].plan(
        {"name": "summarize_notebook_analysis", "arguments": {"shell": "rm -rf /"}}
    )

    result = idempotency.execute_once(bad, "user:ada")

    assert result.status == DENIED  # Commit #4 refuses a non-READY plan
    assert stack["tool"].calls == 0
    assert idempotency.keys() == []


def test_execute_once_rejects_a_non_plan():
    stack = build()

    with pytest.raises(TypeError):
        stack["idempotency"].execute_once(
            {"name": "summarize_notebook_analysis"}, "user:ada"
        )


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


def test_concurrent_duplicate_calls_execute_once():
    stack = build()
    idempotency, tool = stack["idempotency"], stack["tool"]
    plans = [plan_for(stack) for _ in range(8)]
    results = [None] * len(plans)
    barrier = threading.Barrier(len(plans))

    def run(index):
        barrier.wait()
        results[index] = idempotency.execute_once(plans[index], "user:ada")

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(plans))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert tool.calls == 1
    assert len({r.execution_id for r in results}) == 1
    assert all(r.status == SUCCEEDED for r in results)
    assert len(stack["execution"].executions()) == 1


def test_concurrent_distinct_calls_all_execute():
    stack = build()
    idempotency, tool = stack["idempotency"], stack["tool"]
    plans = [plan_for(stack, analysis_id=f"analysis-{i % 2 + 1}") for i in range(6)]
    results = [None] * len(plans)
    barrier = threading.Barrier(len(plans))

    def run(index):
        barrier.wait()
        results[index] = idempotency.execute_once(plans[index], "user:ada")

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(plans))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert tool.calls == 2  # one per distinct argument set
    assert len({r.execution_id for r in results}) == 2


# ---------------------------------------------------------------------------
# audit integration
# ---------------------------------------------------------------------------


def test_only_genuine_executions_reach_the_audit_trail():
    stack = build(with_audit=True)
    idempotency, audit = stack["idempotency"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")

    executed = idempotency.execute_once(plan, "user:ada")
    idempotency.execute_once(plan, "user:ada")  # reuse -- nothing new ran
    idempotency.execute_once(plan, "user:ada")

    trail = audit.trail(plan.plan_id)
    assert [a.status for a in trail] == ["PLANNED", SUCCEEDED]
    assert audit.get(executed.execution_id).execution_id == executed.execution_id
