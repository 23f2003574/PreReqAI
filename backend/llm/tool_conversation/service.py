from ..context import LLMContextItem, LLMContextService
from ..routing import LLMRouteRequest
from ..tool_invocation import READY, LLMToolInvocationService, MalformedToolCallError
from ..tool_permissions import LLMToolPermissionService
from ..tool_results import LLMToolResult, LLMToolResultService
from .models import (
    ASSISTANT_ROLE,
    BLOCKED,
    FINAL_RESPONSE,
    TOOL_CALL,
    ConversationOrderError,
    LLMToolConversationAction,
    LLMToolConversationRequest,
)


class LLMToolConversationService:
    """Drives one tool-calling conversation over the existing LLM pipeline.

    There is no second agent framework here. Every part is an existing
    service doing the job it already does:

        LLMContextService                -- the transcript. Tool results and
                                            assistant turns are appended as
                                            LLMContextItems, so ordering is
                                            the context's own append order
                                            and build() emits the messages
        LLMRequestOrchestrationService   -- every turn. Routing, caching,
                                            retries, fallback, usage, cost,
                                            auditing and the budget check all
                                            come from it unchanged
        Commit #3 LLMToolInvocationService -- reads the model's tool call and
                                            validates it into a plan
        Commit #4 LLMToolPermissionService -- authorizes that plan
        Commit #6 LLMToolResultService   -- the only way a tool result is
                                            allowed into the transcript

    The loop is bounded twice over. max_tool_calls caps how many tool calls
    one conversation may make, and the budget scope (when configured) caps
    what it may spend -- the orchestration pipeline refuses the turn before
    it reaches a provider, and that refusal surfaces here as BLOCKED.

    Nothing is executed autonomously. next_action() returns a validated,
    authorized plan; running it is the caller's decision, using Commit #5.
    The result comes back through continue_(), which is the only way the
    conversation advances.
    """

    def __init__(
        self,
        orchestration_service,
        context_service: LLMContextService,
        invocation_service: LLMToolInvocationService,
        permission_service: LLMToolPermissionService,
        result_service: LLMToolResultService = None,
        route_request: LLMRouteRequest = None,
    ):
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._invocation_service = invocation_service
        self._permission_service = permission_service
        self._result_service = result_service or LLMToolResultService()
        self._route_request = route_request or LLMRouteRequest(
            task="tool_calling_conversation", required_capabilities=["chat"]
        )
        self._state = {}

    # -- conversation state ------------------------------------------------

    def _get_state(self, request: LLMToolConversationRequest) -> dict:
        return self._state.setdefault(
            request.request_id,
            {"turns": 0, "tool_calls": 0, "pending_plan_id": None},
        )

    def tool_calls_made(self, request_id: str) -> int:
        return self._state.get(request_id, {}).get("tool_calls", 0)

    def pending_plan_id(self, request_id: str):
        """The plan whose result the conversation is currently waiting for."""
        return self._state.get(request_id, {}).get("pending_plan_id")

    @staticmethod
    def _require_request(request):
        if not isinstance(request, LLMToolConversationRequest):
            raise TypeError(
                f"Cannot continue something that is not an "
                f"LLMToolConversationRequest: {request!r}."
            )

    def _blocked(self, request, state, reason, decision=None, errors=None):
        return LLMToolConversationAction(
            request_id=request.request_id,
            kind=BLOCKED,
            reason=reason,
            decision=decision,
            tool_calls_made=state["tool_calls"],
            errors=list(errors or []),
        )

    # -- the loop ----------------------------------------------------------

    def next_action(self, request) -> LLMToolConversationAction:
        """Take one turn: ask the model, and classify what it wants to do.

        Returns a FINAL_RESPONSE, a validated and authorized TOOL_CALL, or
        BLOCKED. Executes nothing.
        """
        self._require_request(request)
        state = self._get_state(request)

        if state["pending_plan_id"] is not None:
            raise ConversationOrderError(
                f"conversation {request.request_id!r} is waiting for the result of "
                f"plan {state['pending_plan_id']!r}; feed it back with continue_() "
                "before taking another turn"
            )

        state["turns"] += 1
        turn_request_id = f"{request.request_id}-turn-{state['turns']}"

        response, decision = self._orchestration_service.execute(
            request.route_request or self._route_request,
            turn_request_id,
            request.context_id,
            budget_scope_id=request.budget_scope_id,
            estimated_tokens=request.estimated_tokens,
            estimated_cost=request.estimated_cost,
            temperature=request.temperature,
        )

        # The orchestration pipeline refuses a turn it cannot afford, cannot
        # route, or cannot complete. Budget exhaustion arrives here.
        if response is None:
            return self._blocked(request, state, decision.reason, decision=decision)

        content = response.content or ""
        if not content.strip():
            return self._blocked(
                request, state, "model returned an empty response", decision=decision
            )

        # Is this a tool call? Commit #3 already knows how to read one, and
        # refuses anything that is not a well-formed call -- which is exactly
        # the signal that this turn was a plain answer instead.
        try:
            plan = self._invocation_service.plan(content)
        except MalformedToolCallError:
            self._append(request.context_id, ASSISTANT_ROLE, content)
            return LLMToolConversationAction(
                request_id=request.request_id,
                kind=FINAL_RESPONSE,
                content=content,
                reason="model produced a final response",
                decision=decision,
                tool_calls_made=state["tool_calls"],
            )

        # A tool call. Record it in the transcript first, so the result that
        # follows it is paired with it in order.
        self._append(request.context_id, ASSISTANT_ROLE, content)

        if state["tool_calls"] >= request.max_tool_calls:
            return self._blocked(
                request,
                state,
                f"tool-call limit of {request.max_tool_calls} reached for "
                f"conversation {request.request_id!r}",
                decision=decision,
            )

        # Commit #3 has already validated the call against Commit #1/#2. A
        # call that did not survive that never becomes an executable plan.
        if plan.status != READY:
            return self._blocked(
                request,
                state,
                f"tool call rejected: {plan.rationale}",
                decision=decision,
                errors=plan.errors,
            )

        # Commit #4 decides whether this subject may run it.
        authorization = self._permission_service.authorize(plan, request.subject)
        if not authorization.allowed:
            return self._blocked(
                request, state, authorization.reason, decision=decision
            )

        state["tool_calls"] += 1
        state["pending_plan_id"] = plan.plan_id

        return LLMToolConversationAction(
            request_id=request.request_id,
            kind=TOOL_CALL,
            plan=plan,
            reason=authorization.reason,
            decision=decision,
            tool_calls_made=state["tool_calls"],
        )

    def continue_(self, request, tool_result) -> LLMToolConversationAction:
        """Append a tool result to the transcript and take the next turn.

        Named with a trailing underscore because `continue` is a Python
        keyword -- the PEP 8 spelling of a name that would otherwise
        collide.

        The result must be the Commit #6 LLMToolResult for the tool call
        this conversation is actually waiting on, and must pass that
        service's own validation before it can enter the context.
        """
        self._require_request(request)
        state = self._get_state(request)

        if not isinstance(tool_result, LLMToolResult):
            raise TypeError(
                f"Cannot continue with something that is not an LLMToolResult: "
                f"{tool_result!r}."
            )

        pending = state["pending_plan_id"]
        if pending is None:
            raise ConversationOrderError(
                f"conversation {request.request_id!r} has no outstanding tool call "
                "to answer"
            )

        answered = tool_result.metadata.get("plan_id")
        if answered != pending:
            raise ConversationOrderError(
                f"result answers plan {answered!r} but conversation "
                f"{request.request_id!r} is waiting for {pending!r}"
            )

        # Commit #6's gate: an invalid result never enters LLM context. This
        # raises InvalidToolResultError rather than silently dropping it.
        item = self._result_service.context(tool_result)
        self._context_service.add(request.context_id, item)

        state["pending_plan_id"] = None

        return self.next_action(request)

    # -- transcript --------------------------------------------------------

    def _append(self, context_id: str, item_type: str, content: str):
        return self._context_service.add(
            context_id, LLMContextItem(type=item_type, content=content, priority=0)
        )

    def transcript(self, request) -> list:
        """The conversation so far, as the message dicts build() emits."""
        self._require_request(request)
        return self._context_service.build(request.context_id)["messages"]
