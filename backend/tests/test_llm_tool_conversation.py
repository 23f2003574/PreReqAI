import json

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.budget import LLMBudgetService
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextItem, LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_conversation import (
    BLOCKED,
    ConversationOrderError,
    FINAL_RESPONSE,
    LLMToolConversationRequest,
    LLMToolConversationService,
    TOOL_CALL,
)
from backend.llm.tool_execution import LLMToolExecutionService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tools import LLMToolRegistryService


class ScriptedProvider(LLMProvider):
    """A real LLMProvider replaying one scripted outcome per call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def say(content, tokens=5):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": tokens})


def tool_call(analysis_id="analysis-1", **extra):
    payload = {"name": "summarize_notebook_analysis", "arguments": {"analysis_id": analysis_id}}
    payload.update(extra)
    return json.dumps(payload)


SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {"analysis_id": {"type": "string"}},
    "required": ["analysis_id"],
}

# A real deterministic capability: return the stored summary for an analysis.
SUMMARIES = {"analysis-1": {"cell_count": 3, "code_cell_count": 2}}


def summarize(analysis_id):
    return SUMMARIES[analysis_id]


def build(script, budget=None, max_tool_calls=5, allow_tool=True):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(
            provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True
        )
    )
    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    budget_service = None
    if budget is not None:
        budget_service = LLMBudgetService()
        budget_service.configure("workspace-1", max_tokens=budget)

    orchestration = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider(script)},
        budget_service=budget_service,
    )

    registry = LLMToolRegistryService()
    registry.register(
        "summarize_notebook_analysis",
        "Summarize a notebook analysis.",
        SUMMARIZE_SCHEMA,
    )
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    if allow_tool:
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="allow-1",
                tool_name="summarize_notebook_analysis",
                subject=ANY_SUBJECT,
                allowed=True,
            )
        )
    results = LLMToolResultService()
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", summarize)

    conversation = LLMToolConversationService(
        orchestration, context_service, invocation, permissions, results
    )

    # The caller owns the transcript, using the existing context service.
    context_service.create("conversation-1", system="You may call tools.")
    context_service.add(
        "conversation-1",
        LLMContextItem(type="user", content="How big is analysis-1?", priority=0),
    )

    request = LLMToolConversationRequest(
        request_id="conversation-1",
        context_id="conversation-1",
        subject="user:ada",
        budget_scope_id="workspace-1" if budget is not None else None,
        estimated_tokens=10 if budget is not None else 0,
        max_tool_calls=max_tool_calls,
    )

    return {
        "conversation": conversation,
        "request": request,
        "context_service": context_service,
        "registry": registry,
        "execution": execution,
        "results": results,
        "permissions": permissions,
        "budget_service": budget_service,
    }


def run_tool(stack, action):
    """What a caller does between turns: execute, then normalize."""
    record = stack["execution"].execute(action.plan, stack["request"].subject)
    return stack["results"].normalize(record)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tool_result_leads_to_a_final_response():
    stack = build([say(tool_call()), say("analysis-1 has 3 cells, 2 of them code.")])
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    assert first.kind == TOOL_CALL
    assert first.plan.tool_name == "summarize_notebook_analysis"
    assert first.tool_calls_made == 1

    result = run_tool(stack, first)
    assert result.output == {"cell_count": 3, "code_cell_count": 2}

    final = conversation.continue_(request, result)

    assert final.kind == FINAL_RESPONSE
    assert final.content == "analysis-1 has 3 cells, 2 of them code."
    assert final.tool_calls_made == 1


def test_tool_result_leads_to_another_tool_call():
    stack = build([say(tool_call()), say(tool_call()), say("done")])
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    second = conversation.continue_(request, run_tool(stack, first))

    assert second.kind == TOOL_CALL
    assert second.tool_calls_made == 2
    assert second.plan.plan_id != first.plan.plan_id

    third = conversation.continue_(request, run_tool(stack, second))
    assert third.kind == FINAL_RESPONSE


def test_context_ordering():
    """assistant tool call, then its result, then the next assistant turn."""
    stack = build([say(tool_call()), say("all done")])
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    conversation.continue_(request, run_tool(stack, first))

    messages = conversation.transcript(request)

    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert json.loads(messages[1]["content"])["name"] == "summarize_notebook_analysis"
    assert json.loads(messages[2]["content"])["output"] == {
        "cell_count": 3,
        "code_cell_count": 2,
    }
    assert messages[3]["content"] == "all done"


def test_a_result_must_answer_the_outstanding_call():
    stack = build([say(tool_call()), say("done")])
    conversation, request = stack["conversation"], stack["request"]
    first = conversation.next_action(request)
    result = run_tool(stack, first)

    # A result for some other plan cannot be spliced in.
    import dataclasses

    mismatched = dataclasses.replace(
        result, metadata=dict(result.metadata, plan_id="tool-plan-someone-else-9")
    )
    with pytest.raises(ConversationOrderError, match="waiting for"):
        conversation.continue_(request, mismatched)

    # The real one still works, and ordering is intact.
    assert conversation.continue_(request, result).kind == FINAL_RESPONSE


def test_continue_without_an_outstanding_call_is_refused():
    stack = build([say(tool_call()), say("just an answer")])
    conversation, request = stack["conversation"], stack["request"]
    first = conversation.next_action(request)
    result = run_tool(stack, first)
    conversation.continue_(request, result)  # settles the outstanding call

    with pytest.raises(ConversationOrderError, match="no outstanding tool call"):
        conversation.continue_(request, result)


def test_continue_rejects_a_non_result():
    stack = build([say(tool_call())])
    conversation, request = stack["conversation"], stack["request"]
    conversation.next_action(request)

    with pytest.raises(TypeError):
        conversation.continue_(request, {"status": "SUCCEEDED"})


def test_taking_a_turn_while_a_call_is_outstanding_is_refused():
    stack = build([say(tool_call()), say("done")])
    conversation, request = stack["conversation"], stack["request"]
    conversation.next_action(request)

    with pytest.raises(ConversationOrderError, match="waiting for the result"):
        conversation.next_action(request)


def test_invalid_next_tool_call_is_blocked_not_executed():
    """A call whose arguments fail Commit #2/#3 validation never becomes a plan
    the caller can run."""
    bad_call = json.dumps(
        {"name": "summarize_notebook_analysis", "arguments": {"shell": "rm -rf /"}}
    )
    stack = build([say(bad_call)])
    conversation, request = stack["conversation"], stack["request"]

    action = conversation.next_action(request)

    assert action.kind == BLOCKED
    assert action.plan is None
    assert "rejected" in action.reason
    assert {e.rule for e in action.errors}
    assert conversation.pending_plan_id(request.request_id) is None


def test_a_call_to_an_unregistered_tool_is_blocked():
    stack = build([say(json.dumps({"name": "run_shell", "arguments": {}}))])
    conversation, request = stack["conversation"], stack["request"]

    action = conversation.next_action(request)

    assert action.kind == BLOCKED
    assert [e.rule for e in action.errors] == ["unknown_tool"]


def test_an_unauthorized_tool_call_is_blocked():
    stack = build([say(tool_call())], allow_tool=False)
    conversation, request = stack["conversation"], stack["request"]

    action = conversation.next_action(request)

    assert action.kind == BLOCKED
    assert "denied by default" in action.reason
    assert action.tool_calls_made == 0


def test_an_explicit_deny_blocks_the_call():
    stack = build([say(tool_call())])
    stack["permissions"].register(
        LLMToolPermissionPolicy(
            policy_id="deny-ada",
            tool_name="summarize_notebook_analysis",
            subject="user:ada",
            allowed=False,
        )
    )

    action = stack["conversation"].next_action(stack["request"])

    assert action.kind == BLOCKED
    assert "explicitly denies" in action.reason


def test_a_disabled_tool_blocks_the_call():
    stack = build([say(tool_call())])
    stack["registry"].disable("summarize_notebook_analysis")

    action = stack["conversation"].next_action(stack["request"])

    assert action.kind == BLOCKED
    assert [e.rule for e in action.errors] == ["disabled_tool"]


def test_loop_limit_handling():
    """The conversation is cut off after max_tool_calls, however many more the
    model asks for."""
    stack = build([say(tool_call())], max_tool_calls=2)
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    second = conversation.continue_(request, run_tool(stack, first))
    assert (first.kind, second.kind) == (TOOL_CALL, TOOL_CALL)
    assert second.tool_calls_made == 2

    third = conversation.continue_(request, run_tool(stack, second))

    assert third.kind == BLOCKED
    assert "tool-call limit of 2 reached" in third.reason
    assert third.tool_calls_made == 2
    assert conversation.pending_plan_id(request.request_id) is None


def test_a_zero_tool_call_limit_permits_no_tools_at_all():
    stack = build([say(tool_call())], max_tool_calls=0)

    action = stack["conversation"].next_action(stack["request"])

    assert action.kind == BLOCKED
    assert "tool-call limit of 0 reached" in action.reason


def test_budget_exhaustion():
    """The existing budget service refuses the turn; the loop reports it."""
    stack = build([say(tool_call()), say("done")], budget=12)
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    assert first.kind == TOOL_CALL

    # The first turn consumed the scope's tokens; the next one cannot afford
    # its own estimate.
    action = conversation.continue_(request, run_tool(stack, first))

    assert action.kind == BLOCKED
    assert "budget exceeded" in action.reason
    assert action.decision.allowed is False


def test_budget_is_enforced_by_the_existing_service_not_re_implemented():
    stack = build([say(tool_call())], budget=1)
    conversation, request = stack["conversation"], stack["request"]

    action = conversation.next_action(request)

    assert action.kind == BLOCKED
    assert "budget exceeded" in action.reason
    # Nothing was appended to the transcript for a turn that never happened.
    assert [m["role"] for m in conversation.transcript(request)] == ["user"]


def test_an_empty_model_response_is_blocked():
    stack = build([say("   ")])

    action = stack["conversation"].next_action(stack["request"])

    assert action.kind == BLOCKED
    assert "empty response" in action.reason


def test_a_failed_tool_result_still_advances_the_conversation():
    """A tool that failed is reported to the model, which answers anyway."""
    stack = build([say(tool_call("analysis-missing")), say("I could not find that analysis.")])
    conversation, request = stack["conversation"], stack["request"]

    first = conversation.next_action(request)
    result = run_tool(stack, first)
    assert result.status == "FAILED"

    final = conversation.continue_(request, result)

    assert final.kind == FINAL_RESPONSE
    messages = conversation.transcript(request)
    assert json.loads(messages[2]["content"])["status"] == "FAILED"
    assert "KeyError" in json.loads(messages[2]["content"])["error"]


def test_the_conversation_never_executes_a_tool_itself():
    """next_action returns a proposal; only the caller runs it."""
    stack = build([say(tool_call()), say("done")])
    conversation, request = stack["conversation"], stack["request"]

    for attr in ("invoke", "call", "execute", "run", "dispatch", "bind"):
        assert not hasattr(conversation, attr)

    action = conversation.next_action(request)

    assert action.kind == TOOL_CALL
    # Nothing ran: no execution was recorded anywhere.
    assert stack["execution"].executions() == []


def test_request_validation():
    for kwargs in (
        {"request_id": ""},
        {"context_id": ""},
        {"max_tool_calls": -1},
        {"max_tool_calls": "3"},
    ):
        fields = {
            "request_id": "conversation-1",
            "context_id": "conversation-1",
            "subject": "user:ada",
        }
        fields.update(kwargs)
        with pytest.raises(ValueError):
            LLMToolConversationRequest(**fields)


def test_service_rejects_a_non_request():
    stack = build([say("hi")])

    with pytest.raises(TypeError):
        stack["conversation"].next_action({"request_id": "conversation-1"})
