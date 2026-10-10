import dataclasses
from datetime import datetime, timezone
from threading import RLock

from ..tool_execution import DENIED, REJECTED, SUCCEEDED, LLMToolExecution
from ..tool_invocation import READY, LLMToolInvocationPlan, MalformedToolCallError
from ..tool_results import LLMToolResultService
from .models import LLMToolCallDecision


class UnknownToolCallDecisionError(KeyError):
    """Raised when decision() is given an id with no recorded decision."""


class LLMToolCallingOrchestrationService:
    """Sequences the whole tool-calling pipeline into one bounded path.

    This is the tool-calling counterpart of LLMRequestOrchestrationService,
    and it is built the same way that service is: every collaborator is an
    existing service from an earlier commit, and this one adds no behavior
    of its own. It only calls into them in a fixed order:

        plan (#3, which validates via #2 against #1)
          -> authorize (#4)
          -> execute (#11 retry over #10 timeout over #9 idempotency over #5)
          -> normalize (#6)
          -> audit (#8) and measure (#12)
          -> record one decision

    Ordering is the point, and it matches the rules exactly. A tool call is
    planned and validated before anyone is authorized for it; authorization
    is settled before any executor is entered, so a denied subject never
    reaches idempotency, a timer, or a handler; and the result is normalized
    before it can go back to the model.

    Execution depth is whatever the caller wired. The outermost executor
    available is used -- retry if present, else timeout control, else
    idempotency, else the bare Commit #5 engine -- so a caller opts into
    exactly the guarantees they want without this service reimplementing
    any of them.

    Nothing arbitrary can run. The model supplies a tool *name* and
    arguments; a name only executes if it is registered, enabled, bound by
    the application, schema-valid and authorized. This service adds no way
    around that, and holds no handlers of its own.

    Audit wiring: this service owns the audit lifecycle -- start,
    authorization, execution, complete. Pass the audit service *here*, not
    also into the Commit #9/#10/#11 services, or each attempt would be
    recorded twice. Commit #11 remains the right place to wire it instead
    if per-attempt snapshots matter more than a single owner; do one or the
    other, not both.

    Conversation continuation stays caller-driven. continue_conversation()
    hands a tool result back to Commit #7 and returns the next action --
    it does not then execute that action itself. Commit #7's guarantee that
    no tool runs without the caller deciding to run it is preserved here
    rather than quietly dropped at the top of the stack.
    """

    def __init__(
        self,
        invocation_service,
        permission_service,
        execution_service=None,
        result_service: LLMToolResultService = None,
        idempotency_service=None,
        control_service=None,
        retry_service=None,
        conversation_service=None,
        audit_service=None,
        metrics_service=None,
        default_timeout=None,
    ):
        if not any(
            (retry_service, control_service, idempotency_service, execution_service)
        ):
            raise ValueError(
                "an executor is required: pass a retry (#11), control (#10), "
                "idempotency (#9) or execution (#5) service"
            )

        self._invocation_service = invocation_service
        self._permission_service = permission_service
        self._execution_service = execution_service
        self._result_service = result_service or LLMToolResultService()
        self._idempotency_service = idempotency_service
        self._control_service = control_service
        self._retry_service = retry_service
        self._conversation_service = conversation_service
        self._audit_service = audit_service
        self._metrics_service = metrics_service
        self._default_timeout = default_timeout

        self._decisions = {}
        self._counter = 0
        self._lock = RLock()

    # -- decisions ---------------------------------------------------------

    def _record(self, **fields) -> LLMToolCallDecision:
        with self._lock:
            self._counter += 1
            decision = LLMToolCallDecision(
                decision_id=f"tool-decision-{self._counter}",
                created_at=datetime.now(timezone.utc),
                **fields,
            )
            # Reachable by whichever identifier the caller has.
            for key in (decision.decision_id, decision.execution_id, decision.plan_id):
                if key:
                    self._decisions[key] = decision
            return decision

    def decision(self, execution_id: str) -> LLMToolCallDecision:
        """The final decision for one call, by execution, plan or decision id."""
        with self._lock:
            try:
                return self._decisions[execution_id]
            except KeyError:
                raise UnknownToolCallDecisionError(execution_id)

    def decisions(self) -> list:
        with self._lock:
            unique = {}
            for decision in self._decisions.values():
                unique.setdefault(decision.decision_id, decision)
            return list(unique.values())

    # -- the pipeline ------------------------------------------------------

    def _plan(self, tool_call):
        """Step 1: read and validate the call. Commit #3, over #2 over #1."""
        if isinstance(tool_call, LLMToolInvocationPlan):
            return tool_call
        return self._invocation_service.plan(tool_call)

    def _execute(self, plan, subject, timeout):
        """Step 3: run through the outermost executor the caller wired."""
        if self._retry_service is not None:
            return self._retry_service.execute(plan, subject, timeout=timeout)

        if timeout is not None:
            if self._control_service is None:
                raise ValueError(
                    "a control (#10) or retry (#11) service is required to honour "
                    "a timeout"
                )
            return self._control_service.execute_with_timeout(plan, subject, timeout)

        if self._control_service is not None and self._idempotency_service is None:
            return self._control_service.execution_service.execute(plan, subject)

        if self._idempotency_service is not None:
            return self._idempotency_service.execute_once(plan, subject)

        return self._execution_service.execute(plan, subject)

    def _attempts_for(self, execution: LLMToolExecution) -> int:
        if self._retry_service is None:
            return 1
        return self._retry_service.attempts(execution.execution_id) or 1

    def execute(self, tool_call, subject, request_id: str = None, timeout=None):
        """Run one tool call end to end and return its single final decision.

        Accepts a raw tool call (dict or JSON text) or an already-planned
        Commit #3 plan, so an action produced by the conversation loop can be
        executed without being re-read.
        """
        timeout = self._default_timeout if timeout is None else timeout

        # 1. Validate, by planning. A call too malformed to name a tool has
        #    nothing to plan or authorize.
        try:
            plan = self._plan(tool_call)
        except MalformedToolCallError as exc:
            return self._record(
                request_id=request_id, plan_id=None, execution_id=None,
                tool_name=None, status=REJECTED, allowed=False,
                reason=f"malformed tool call: {exc}",
            )

        request_id = request_id or f"tool-call-{plan.plan_id}"

        if self._audit_service is not None:
            self._audit_service.start(plan, request_id, subject=subject)

        # A call that failed Commit #2 validation is refused before anyone is
        # authorized for it.
        if plan.status != READY:
            return self._finish(
                request_id, plan, None, REJECTED, False,
                f"tool call rejected: {plan.rationale}",
            )

        # 2. Authorize, before any executor is entered.
        authorization = self._permission_service.authorize(plan, subject)
        if self._audit_service is not None:
            self._audit_service.record_authorization(plan.plan_id, authorization)

        if not authorization.allowed:
            return self._finish(
                request_id, plan, None, DENIED, False, authorization.reason
            )

        # 3. Execute, at whatever depth the caller wired.
        execution = self._execute(plan, subject, timeout)

        return self._finish(
            request_id,
            plan,
            execution,
            execution.status,
            execution.status == SUCCEEDED,
            execution.error or execution.status,
        )

    def _finish(self, request_id, plan, execution, status, allowed, reason):
        """Steps 4-6: normalize, audit, measure, and record one decision."""
        normalized = None
        attempts = 0
        duration = None
        execution_id = None

        if execution is not None:
            execution_id = execution.execution_id
            attempts = self._attempts_for(execution)

            # 4. Normalize before anything goes back to the model.
            normalized = self._stamp(self._result_service.normalize(execution), plan)

            # 5. Audit and measure the outcome.
            if self._audit_service is not None:
                self._audit_service.record_execution(execution)
                self._audit_service.complete(execution_id, status)

            if self._metrics_service is not None:
                measured = self._metrics_service.record(execution)
                duration = measured.duration
                attempts = measured.attempts

        return self._record(
            request_id=request_id,
            plan_id=plan.plan_id if plan is not None else None,
            execution_id=execution_id,
            tool_name=plan.tool_name if plan is not None else None,
            status=status,
            allowed=allowed,
            reason=reason,
            attempts=attempts,
            duration=duration,
            result=normalized,
        )

    @staticmethod
    def _stamp(normalized, plan):
        """Make a result name the plan it answers.

        Commit #9 hands back the original execution when a duplicate call is
        de-duplicated, and that record carries the *first* plan's id. Commit
        #7 checks a result against the plan it is waiting for, so an
        unstamped reuse would be refused as out of order -- the model asked
        the same question twice and would be told its own answer belongs to
        someone else.

        The re-stamp is a correction, not a fiction: the result genuinely
        answers this plan, and where the work actually ran is preserved both
        in reused_execution_of_plan and on the execution record itself, which
        is what the audit trail links to.
        """
        if plan is None or normalized.metadata.get("plan_id") == plan.plan_id:
            return normalized

        metadata = dict(
            normalized.metadata,
            plan_id=plan.plan_id,
            reused_execution_of_plan=normalized.metadata.get("plan_id"),
        )
        return dataclasses.replace(normalized, metadata=metadata)

    # -- conversation ------------------------------------------------------

    def continue_conversation(self, request, result):
        """Feed a tool result back to Commit #7 and return the next action.

        Commit #7 owns the transcript, the ordering rules and the tool-call
        limit; this method adds nothing to them. It deliberately does not
        execute a TOOL_CALL action it receives -- the caller does that, via
        execute(), so no tool ever runs without a caller asking for it.
        """
        if self._conversation_service is None:
            raise ValueError("a conversation service (#7) is required")
        return self._conversation_service.continue_(request, result)

    def next_action(self, request):
        """The conversation's next turn, unchanged from Commit #7."""
        if self._conversation_service is None:
            raise ValueError("a conversation service (#7) is required")
        return self._conversation_service.next_action(request)
