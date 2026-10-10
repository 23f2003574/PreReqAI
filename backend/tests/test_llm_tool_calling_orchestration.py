import json
import threading
import time

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextItem, LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.retry import TransientLLMError
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_conversation import (
    BLOCKED,
    FINAL_RESPONSE,
    LLMToolConversationRequest,
    LLMToolConversationService,
    TOOL_CALL,
)
from backend.llm.tool_execution import (
    CANCELLED,
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
)
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_metrics import LLMToolMetricsService
from backend.llm.tool_orchestration import (
    LLMToolCallingOrchestrationService,
    UnknownToolCallDecisionError,
)
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
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


class ScriptedProvider(LLMProvider):
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        return self._script[min(self.calls - 1, len(self._script) - 1)]

    def stream(self, request):
        raise NotImplementedError


def say(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 5})


def tool_call(analysis_id="analysis-1", **extra):
    payload = {
        "name": "summarize_notebook_analysis",
        "arguments": dict({"analysis_id": analysis_id}, **extra),
    }
    return payload


class Tool:
    def __init__(self, failures=0, delay=0.0, error=None):
        self.failures = failures
        self.delay = delay
        self.error = error or TransientLLMError("upstream is briefly unavailable")
        self.calls = 0

    def __call__(self, analysis_id, api_key=None):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.calls <= self.failures:
            raise self.error
        return SUMMARIES[analysis_id]


def build(tool=None, allow=True, script=None, policy=None, timeout=None):
    registry = LLMToolRegistryService()
    registry.register(
        "summarize_notebook_analysis",
        "Summarize a notebook analysis via LLMNotebookAnalysisService.summary.",
        SUMMARIZE_SCHEMA,
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

    tool = tool if tool is not None else Tool()
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", tool)

    idempotency = LLMToolIdempotencyService(execution, permissions)
    control = LLMToolExecutionControlService(execution, idempotency)
    # Audit is wired into the orchestrator only -- one owner, as documented.
    retry = LLMToolRetryService(
        control,
        execution,
        policy or LLMToolRetryPolicy(max_attempts=3, backoff=0.0),
        sleeper=lambda seconds: None,
        idempotency_service=idempotency,
    )
    audit = LLMToolAuditService()
    metrics = LLMToolMetricsService(retry)
    results = LLMToolResultService()

    context_service = LLMContextService()
    conversation = None
    if script is not None:
        config_service = LLMProviderConfigService()
        config_service.register(
            LLMProviderConfig(
                provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True
            )
        )
        routing = LLMModelRoutingService(config_service)
        routing.register_capability_profile(
            "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
        )
        llm_orchestration = LLMRequestOrchestrationService(
            context_service=context_service,
            routing_service=routing,
            providers={"openai": ScriptedProvider(script)},
        )
        conversation = LLMToolConversationService(
            llm_orchestration, context_service, invocation, permissions, results
        )

    orchestrator = LLMToolCallingOrchestrationService(
        invocation_service=invocation,
        permission_service=permissions,
        execution_service=execution,
        result_service=results,
        idempotency_service=idempotency,
        control_service=control,
        retry_service=retry,
        conversation_service=conversation,
        audit_service=audit,
        metrics_service=metrics,
        default_timeout=timeout,
    )

    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "execution": execution,
        "idempotency": idempotency,
        "control": control,
        "retry": retry,
        "audit": audit,
        "metrics": metrics,
        "results": results,
        "context_service": context_service,
        "conversation": conversation,
        "orchestrator": orchestrator,
        "tool": tool,
    }


@pytest.fixture(autouse=True)
def _shutdown_pools():
    created = []
    original = LLMToolExecutionControlService.__init__

    def tracking_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        created.append(self)

    LLMToolExecutionControlService.__init__ = tracking_init
    try:
        yield
    finally:
        LLMToolExecutionControlService.__init__ = original
        for service in created:
            service.shutdown(wait=False)


# ---------------------------------------------------------------------------
# the happy path
# ---------------------------------------------------------------------------


def test_successful_tool_call():
    stack = build()

    decision = stack["orchestrator"].execute(tool_call(), "user:ada", request_id="conv-1")

    assert decision.status == SUCCEEDED
    assert decision.allowed is True
    assert decision.tool_name == "summarize_notebook_analysis"
    assert decision.request_id == "conv-1"
    assert decision.plan_id is not None
    assert decision.execution_id is not None
    assert decision.attempts == 1
    assert decision.duration is not None
    # The result is normalized (Commit #6), ready for the model.
    assert decision.result.status == SUCCEEDED
    assert decision.result.output == {"cell_count": 3, "code_cell_count": 2}
    assert stack["results"].validate(decision.result) is True


def test_one_deterministic_final_decision_reachable_by_any_id():
    stack = build()
    orchestrator = stack["orchestrator"]

    decision = orchestrator.execute(tool_call(), "user:ada")

    assert orchestrator.decision(decision.execution_id) is decision
    assert orchestrator.decision(decision.plan_id) is decision
    assert orchestrator.decision(decision.decision_id) is decision
    assert orchestrator.decisions() == [decision]

    with pytest.raises(UnknownToolCallDecisionError):
        orchestrator.decision("does-not-exist")


def test_a_json_tool_call_and_a_plan_are_both_accepted():
    stack = build()
    orchestrator, invocation = stack["orchestrator"], stack["invocation"]

    from_json = orchestrator.execute(json.dumps(tool_call()), "user:ada")
    assert from_json.status == SUCCEEDED

    plan = invocation.plan(tool_call(analysis_id="analysis-1"))
    from_plan = orchestrator.execute(plan, "user:ada")
    assert from_plan.status == SUCCEEDED
    assert from_plan.plan_id == plan.plan_id


# ---------------------------------------------------------------------------
# gates, in order
# ---------------------------------------------------------------------------


def test_validation_rejection_happens_before_authorization():
    stack = build()
    bad = dict(tool_call(), arguments={"shell": "rm -rf /"})

    decision = stack["orchestrator"].execute(bad, "user:ada")

    assert decision.status == REJECTED
    assert decision.allowed is False
    assert decision.execution_id is None
    assert "rejected" in decision.reason
    assert stack["tool"].calls == 0
    # No authorization was recorded, because none was sought.
    assert [a.status for a in stack["audit"].trail(decision.plan_id)] == ["PLANNED"]


def test_a_malformed_call_is_refused_without_a_plan():
    stack = build()

    decision = stack["orchestrator"].execute({"arguments": {}}, "user:ada")

    assert decision.status == REJECTED
    assert decision.plan_id is None
    assert decision.execution_id is None
    assert "malformed" in decision.reason
    assert stack["tool"].calls == 0


def test_permission_rejection_happens_before_execution():
    stack = build(allow=False)

    decision = stack["orchestrator"].execute(tool_call(), "user:ada")

    assert decision.status == DENIED
    assert decision.allowed is False
    assert decision.execution_id is None
    assert "denied by default" in decision.reason
    assert stack["tool"].calls == 0
    # A denied subject never reached idempotency either.
    assert stack["idempotency"].keys() == []
    assert [a.status for a in stack["audit"].trail(decision.plan_id)] == [
        "PLANNED",
        DENIED,
    ]


def test_a_disabled_tool_is_refused():
    stack = build()
    plan = stack["invocation"].plan(tool_call())
    stack["registry"].disable("summarize_notebook_analysis")

    decision = stack["orchestrator"].execute(plan, "user:ada")

    assert decision.status == DENIED  # Commit #4's registry gate
    assert stack["tool"].calls == 0


def test_no_arbitrary_execution_surface():
    stack = build()
    orchestrator = stack["orchestrator"]

    for attr in ("bind", "invoke", "call", "run", "dispatch", "eval"):
        assert not hasattr(orchestrator, attr)

    # An unregistered tool cannot be reached at all.
    decision = orchestrator.execute({"name": "run_shell", "arguments": {}}, "user:ada")
    assert decision.status == REJECTED


# ---------------------------------------------------------------------------
# idempotency, retry, timeout
# ---------------------------------------------------------------------------


def test_duplicate_call_runs_the_tool_once():
    stack = build()
    orchestrator = stack["orchestrator"]

    first = orchestrator.execute(tool_call(), "user:ada")
    second = orchestrator.execute(tool_call(), "user:ada")

    assert first.status == second.status == SUCCEEDED
    assert stack["tool"].calls == 1
    assert second.execution_id == first.execution_id
    # Two decisions, one execution -- each call still gets its own verdict.
    assert first.decision_id != second.decision_id


def test_a_reused_result_names_the_plan_it_answers():
    """De-duplication must not make a result look out of order to Commit #7,
    while still recording where the work actually ran."""
    stack = build()
    orchestrator, invocation = stack["orchestrator"], stack["invocation"]

    first = orchestrator.execute(tool_call(), "user:ada")
    second_plan = invocation.plan(tool_call())
    second = orchestrator.execute(second_plan, "user:ada")

    assert stack["tool"].calls == 1
    assert second.execution_id == first.execution_id
    # The result answers the plan that was asked...
    assert second.result.metadata["plan_id"] == second_plan.plan_id
    # ...and says plainly where the work actually ran.
    assert second.result.metadata["reused_execution_of_plan"] == first.plan_id
    assert stack["results"].validate(second.result) is True


def test_retry_is_enforced_and_counted():
    stack = build(tool=Tool(failures=2))

    decision = stack["orchestrator"].execute(tool_call(), "user:ada")

    assert decision.status == SUCCEEDED
    assert decision.attempts == 3
    assert stack["tool"].calls == 3
    assert stack["metrics"].get(decision.execution_id).attempts == 3


def test_tool_failure_is_reported_not_raised():
    from backend.llm.retry import PermanentLLMError

    stack = build(tool=Tool(failures=5, error=PermanentLLMError("bad request")))

    decision = stack["orchestrator"].execute(tool_call(), "user:ada")

    assert decision.status == FAILED
    assert decision.allowed is False
    assert decision.attempts == 1  # permanent failures are not retried
    assert decision.result.status == FAILED
    assert decision.result.output is None


def test_timeout_is_enforced():
    stack = build(
        tool=Tool(delay=0.4),
        policy=LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
        timeout=0.05,
    )

    decision = stack["orchestrator"].execute(tool_call(), "user:ada")

    assert decision.status == TIMED_OUT
    assert decision.allowed is False
    assert decision.result.status == TIMED_OUT
    assert "deadline" in decision.result.error
    time.sleep(0.6)


def test_cancellation_produces_a_cancelled_decision():
    stack = build(tool=Tool(delay=0.3))
    orchestrator, control = stack["orchestrator"], stack["control"]
    outcome = {}

    def run():
        outcome["decision"] = orchestrator.execute(tool_call(), "user:ada", timeout=5)

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.08)
    control.cancel("tool-control-1", reason="user pressed stop")
    worker.join(timeout=5)

    assert outcome["decision"].status == CANCELLED
    assert outcome["decision"].allowed is False
    assert outcome["decision"].result.status == CANCELLED
    time.sleep(0.4)


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------


def _conversation(stack, system="You may call tools."):
    stack["context_service"].create("conv-1", system=system)
    stack["context_service"].add(
        "conv-1",
        LLMContextItem(type="user", content="How big is analysis-1?", priority=0),
    )
    return LLMToolConversationRequest(
        request_id="conv-1",
        context_id="conv-1",
        subject="user:ada",
        max_tool_calls=2,
    )


def test_result_feeds_the_next_llm_action():
    stack = build(script=[say(json.dumps(tool_call())), say("analysis-1 has 3 cells.")])
    orchestrator = stack["orchestrator"]
    request = _conversation(stack)

    action = orchestrator.next_action(request)
    assert action.kind == TOOL_CALL

    decision = orchestrator.execute(action.plan, "user:ada", request_id="conv-1")
    assert decision.status == SUCCEEDED

    final = orchestrator.continue_conversation(request, decision.result)

    assert final.kind == FINAL_RESPONSE
    assert final.content == "analysis-1 has 3 cells."
    roles = [m["role"] for m in stack["conversation"].transcript(request)]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_loop_limit_is_enforced():
    stack = build(script=[say(json.dumps(tool_call()))])
    orchestrator = stack["orchestrator"]
    request = _conversation(stack)  # max_tool_calls=2

    first = orchestrator.next_action(request)
    d1 = orchestrator.execute(first.plan, "user:ada", request_id="conv-1")
    second = orchestrator.continue_conversation(request, d1.result)
    assert second.kind == TOOL_CALL

    d2 = orchestrator.execute(second.plan, "user:ada", request_id="conv-1")
    third = orchestrator.continue_conversation(request, d2.result)

    assert third.kind == BLOCKED
    assert "tool-call limit of 2 reached" in third.reason


def test_continuation_does_not_execute_by_itself():
    """Commit #7's guarantee survives at the top of the stack."""
    stack = build(script=[say(json.dumps(tool_call())), say("done")])
    orchestrator = stack["orchestrator"]
    request = _conversation(stack)

    action = orchestrator.next_action(request)

    assert action.kind == TOOL_CALL
    assert stack["tool"].calls == 0
    assert stack["execution"].executions() == []


def test_conversation_methods_need_a_conversation_service():
    stack = build()  # no script -> no conversation service

    with pytest.raises(ValueError, match="conversation service"):
        stack["orchestrator"].next_action(object())
    with pytest.raises(ValueError, match="conversation service"):
        stack["orchestrator"].continue_conversation(object(), object())


# ---------------------------------------------------------------------------
# audit and metrics consistency
# ---------------------------------------------------------------------------


def test_audit_and_metrics_agree_with_the_decision():
    stack = build(tool=Tool(failures=1))
    orchestrator, audit, metrics = stack["orchestrator"], stack["audit"], stack["metrics"]

    decision = orchestrator.execute(tool_call(), "user:ada", request_id="conv-1")

    trail = audit.trail(decision.plan_id)
    assert [a.status for a in trail] == ["PLANNED", "AUTHORIZED", SUCCEEDED, SUCCEEDED]
    assert audit.get(decision.execution_id).status == decision.status
    assert [a.request_id for a in trail] == ["conv-1"] * 4

    measured = metrics.get(decision.execution_id)
    assert measured.status == decision.status
    assert measured.attempts == decision.attempts == 2
    assert measured.duration == decision.duration
    assert measured.tool_name == decision.tool_name


def test_audit_is_recorded_once_per_outcome():
    """Audit is wired into the orchestrator only, so nothing is double-logged."""
    stack = build()
    decision = stack["orchestrator"].execute(tool_call(), "user:ada")

    trail = stack["audit"].trail(decision.plan_id)

    assert len(trail) == 4  # PLANNED, AUTHORIZED, execution, complete
    assert len({a.audit_id for a in trail}) == 4


def test_metrics_aggregate_across_calls():
    stack = build()
    orchestrator = stack["orchestrator"]

    orchestrator.execute(tool_call(), "user:ada")
    orchestrator.execute(tool_call(), "user:grace")  # different subject -> real run
    orchestrator.execute(dict(tool_call(), arguments={"analysis_id": "nope"}), "user:ada")

    summary = stack["metrics"].aggregate("summarize_notebook_analysis")

    assert summary["executions"] == 3
    assert summary["by_status"][SUCCEEDED] == 2
    assert summary["by_status"][FAILED] == 1


def test_secrets_never_reach_the_decision_audit_or_metrics():
    stack = build()
    call = dict(tool_call(), arguments={
        "analysis_id": "analysis-1", "api_key": "sk-abcdefghijklmnopqrst"
    })

    decision = stack["orchestrator"].execute(call, "user:ada")

    import dataclasses

    assert "sk-abcdefghijklmnopqrst" not in repr(dataclasses.asdict(decision))
    assert "sk-abcdefghijklmnopqrst" not in repr(
        dataclasses.asdict(stack["audit"].get(decision.execution_id))
    )
    assert "sk-abcdefghijklmnopqrst" not in repr(
        dataclasses.asdict(stack["metrics"].get(decision.execution_id))
    )


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------


def test_an_executor_is_required():
    registry = LLMToolRegistryService()
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)

    with pytest.raises(ValueError, match="executor is required"):
        LLMToolCallingOrchestrationService(invocation, permissions)


def test_the_bare_execution_service_alone_is_enough():
    """A caller may opt out of idempotency, timeouts and retries."""
    registry = LLMToolRegistryService()
    registry.register("summarize_notebook_analysis", "Summarize.", SUMMARIZE_SCHEMA)
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(
            policy_id="allow-1", tool_name="summarize_notebook_analysis",
            subject=ANY_SUBJECT, allowed=True,
        )
    )
    tool = Tool()
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", tool)
    orchestrator = LLMToolCallingOrchestrationService(
        invocation, permissions, execution_service=execution
    )

    first = orchestrator.execute(tool_call(), "user:ada")
    second = orchestrator.execute(tool_call(), "user:ada")

    assert first.status == second.status == SUCCEEDED
    assert first.attempts == 1
    assert tool.calls == 2  # no idempotency wired, so it genuinely ran twice
    assert first.duration is None  # no metrics wired
