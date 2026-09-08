from backend.agent_capability_execution import LLMAgentCapabilityExecutionService as ExecutionRecordService
from backend.agent_capability_execution_policy import LLMAgentCapabilityExecutionPolicy
from backend.agent_capability_execution_validation import LLMAgentCapabilityExecutionValidator
from backend.agent_capability_registry import LLMAgentCapabilityRegistry, UnknownCapabilityError

from .models import (
    FAILED,
    REJECTED_INVALID_INPUT,
    REJECTED_INVALID_OUTPUT,
    REJECTED_POLICY_DENIED,
    REJECTED_UNKNOWN_CAPABILITY,
    SUCCEEDED,
    CapabilityExecutionResult,
)


class InvalidCapabilityExecutionLifecycleError(ValueError):
    """Raised when execute() is given a missing/blank agent_id/
    capability_id/scope_id, or a context that is not a dict."""


class LLMAgentCapabilityExecutionLifecycleService:
    """Named LLMAgentCapabilityExecutionLifecycleService, not
    LLMAgentCapabilityExecutionService as this commit's own class-name
    suggestion literally reads -- that exact name already belongs to
    Commit #7's own execution-record service
    (backend.agent_capability_execution.LLMAgentCapabilityExecutionService),
    which this class composes as one of its own collaborators (imported
    below as ExecutionRecordService to keep the two straight in this
    module). Reusing the identical class name for a second, unrelated
    class in a different module would satisfy the letter of the request
    while actively working against its own spirit ("compose existing
    services... no unrelated refactors"): this name instead mirrors the
    commit's own title/commit-message ("Agent Capability Execution
    Lifecycle") exactly, and is unambiguous wherever both classes are
    imported together, which every caller of this one necessarily does.

    Coordinates one capability execution attempt end to end --
    pre-execution checks, a durable execution record, the actual
    invocation, and post-execution validation -- entirely by composing
    every earlier commit in this series. Not a second execution, policy,
    or validation engine: every actual decision belongs to whichever
    commit already owns it.

        Commit #1  LLMAgentCapabilityRegistry     -- resolves capability_id
                                                       and its exact current
                                                       version
        Commit #7  LLMAgentCapabilityExecutionService (aliased
                   ExecutionRecordService here to keep this module's own
                   class name distinct) -- opens/closes the durable
                   execution record
        Commit #8  LLMAgentCapabilityExecutionValidator -- validates
                   input_payload/context before execution and the
                   returned output afterward, against the exact version
                   resolved above
        Commit #9  LLMAgentCapabilityExecutionPolicy   -- the real,
                   default-deny authorization verdict

    The one piece this series never built -- an actual mechanism that
    runs a capability's real work -- is deliberately not invented here
    either (Rule: "do not create another execution engine" / "no
    invented runtime infrastructure"). Rather than forcing a coupling
    onto the unrelated backend.llm.tool_execution/backend.llm.tools
    registry (a different identifier namespace this series' own
    capability_id has no guaranteed relationship to -- the exact
    reasoning Commit #9 already used to reject integrating backend.llm.
    tool_permissions), this service accepts `executor` -- a plain
    callable supplied by the application at construction time -- the
    same "a handler is supplied by the application at wiring time, never
    derived from LLM output or invented by the framework" discipline
    backend.llm.tool_execution.LLMToolExecutionService.bind() already
    established for its own handlers, reused here as a constructor
    argument rather than a second bind()/registry mechanism, since this
    service is not itself a per-capability handler registry.

    Commit #6's LLMAgentCapabilitySelector is deliberately never called
    here: execute()'s own signature (Rule/Result, taking capability_id
    directly) already names exactly which capability to run -- selection
    is this service's *caller's* job, one step upstream, not something
    execute() itself repeats or second-guesses.

    Every precondition gates the next step, in order, and any failure
    stops the pipeline immediately (Rule: "any failed precondition must
    prevent execution"): an unknown capability, invalid input, or a
    policy denial all short-circuit before a Commit #7 execution record
    is ever created, and before `executor` is ever called. The record is
    created only once both input validation and policy both pass, is
    always the very last thing checked before invocation, and is always
    closed (complete() or fail()) through Commit #7's own service --
    never mutated directly.

    execute() never retries, schedules, or queues anything, and performs
    no I/O of its own beyond calling the collaborators above and
    `executor` exactly once.
    """

    def __init__(
        self,
        capability_registry: LLMAgentCapabilityRegistry,
        execution_service: ExecutionRecordService,
        execution_validator: LLMAgentCapabilityExecutionValidator,
        execution_policy: LLMAgentCapabilityExecutionPolicy,
        executor,
    ):
        self._capability_registry = capability_registry
        self._execution_service = execution_service
        self._execution_validator = execution_validator
        self._execution_policy = execution_policy
        self._executor = executor

    def execute(
        self, agent_id: str, capability_id: str, scope_id: str, input_payload, context: dict = None
    ) -> CapabilityExecutionResult:
        """Run one capability execution attempt end to end.

        Raises:
            InvalidCapabilityExecutionLifecycleError: If agent_id,
                capability_id, or scope_id is missing/blank, or context
                is given and is not a dict
        """
        self._validate_id(agent_id, "agent_id")
        self._validate_id(capability_id, "capability_id")
        self._validate_id(scope_id, "scope_id")
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            raise InvalidCapabilityExecutionLifecycleError(
                f"context must be a dict, got {type(context).__name__}"
            )

        # 1. Resolve the capability and pin its exact current version --
        # this is the version used for every check and record below,
        # even if the capability's own live version moves on mid-flight.
        try:
            capability = self._capability_registry.get(capability_id)
        except UnknownCapabilityError as error:
            return CapabilityExecutionResult(
                execution_id=None,
                status=REJECTED_UNKNOWN_CAPABILITY,
                output=None,
                validation=None,
                policy_decision=None,
                error=str(error),
            )
        version = capability.version

        # 2. Validate input before execution (Commit #8).
        input_validation = self._execution_validator.validate_start(capability_id, version, input_payload, context)
        if not input_validation.valid:
            return CapabilityExecutionResult(
                execution_id=None,
                status=REJECTED_INVALID_INPUT,
                output=None,
                validation=input_validation,
                policy_decision=None,
                error="input validation failed: " + "; ".join(input_validation.errors),
            )

        # 3. Evaluate execution policy before execution (Commit #9).
        policy_decision = self._execution_policy.evaluate(agent_id, capability_id, scope_id, context)
        if not policy_decision.allowed:
            return CapabilityExecutionResult(
                execution_id=None,
                status=REJECTED_POLICY_DENIED,
                output=None,
                validation=input_validation,
                policy_decision=policy_decision,
                error="policy denied execution: " + "; ".join(policy_decision.denials or policy_decision.reasons),
            )

        # 4. Create the execution record before invoking anything (Commit #7).
        execution = self._execution_service.start(
            agent_id, capability_id, version, scope_id, input_data=input_payload
        )

        # 5. Invoke the existing capability mechanism. Never raises for a
        # failing call -- every attempt reaches a terminal
        # CapabilityExecutionResult, the same "an attempt failing is not
        # a caller error" discipline LLMToolExecutionService.execute()
        # already keeps.
        try:
            output_payload = self._executor(capability_id, input_payload, context)
        except Exception as error:
            self._execution_service.fail(execution.execution_id, error)
            return CapabilityExecutionResult(
                execution_id=execution.execution_id,
                status=FAILED,
                output=None,
                validation=input_validation,
                policy_decision=policy_decision,
                error=str(error),
            )

        # 6. Validate the returned output before marking success (Commit #8).
        output_validation = self._execution_validator.validate_result(capability_id, version, output_payload)
        if not output_validation.valid:
            error_message = "output validation failed: " + "; ".join(output_validation.errors)
            self._execution_service.fail(execution.execution_id, error_message)
            return CapabilityExecutionResult(
                execution_id=execution.execution_id,
                status=REJECTED_INVALID_OUTPUT,
                output=None,
                validation=output_validation,
                policy_decision=policy_decision,
                error=error_message,
            )

        # 7. Complete the execution record through the existing service.
        self._execution_service.complete(execution.execution_id, result=output_payload)

        return CapabilityExecutionResult(
            execution_id=execution.execution_id,
            status=SUCCEEDED,
            output=output_payload,
            validation=output_validation,
            policy_decision=policy_decision,
            error=None,
        )

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidCapabilityExecutionLifecycleError(
                f"{field_name} is required and must be a non-empty string"
            )
