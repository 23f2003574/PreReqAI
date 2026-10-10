import re
from datetime import datetime, timezone

from ..tool_invocation import LLMToolInvocationPlan
from ..tool_permissions import LLMToolPermissionService
from ..tool_validation import LLMToolValidationService
from ..tools import (
    DisabledToolError,
    InvalidToolDefinitionError,
    LLMToolRegistryService,
    UnknownToolError,
)
from .models import DENIED, FAILED, REJECTED, SUCCEEDED, LLMToolExecution

# Same secret-redaction convention already used by
# backend.transformation_audit and backend.api_recommendation_export --
# an all-or-nothing "[REDACTED]" whenever a value looks like a credential.
# Kept local, as those two modules keep their own copies, rather than
# refactoring them here.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

# Backstop against the obvious ways a tool binding could become arbitrary
# code or shell execution. This is not the security boundary -- handlers are
# supplied by the application at wiring time and are never derived from LLM
# output, which is what actually keeps execution bounded -- but binding one
# of these is always a mistake, so it is refused outright.
_FORBIDDEN_HANDLERS = frozenset(
    {"eval", "exec", "compile", "__import__", "system", "popen", "spawn"}
)
_FORBIDDEN_HANDLER_MODULES = frozenset({"subprocess", "os", "pty", "commands"})


def _redact(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            return "[REDACTED]"
    return value


class UnknownExecutionError(KeyError):
    """Raised when status()/result()/get() is given an unrecorded execution_id."""


class ExecutionNotSucceededError(ValueError):
    """Raised when result() is called for an execution that did not succeed.

    A failed execution has no result, and returning None for one would let a
    caller mistake "it did not run" for "it returned nothing".
    """


class InvalidToolHandlerError(ValueError):
    """Raised when bind() is given something that must not become a tool."""


class LLMToolExecutionService:
    """Runs an authorized Commit #3 plan against a real project service (Commit #5).

    Every gate in front of execution is an earlier commit's, re-used rather
    than re-implemented:

        Commit #1 registry      -- the tool exists and is enabled
        Commit #2 validation    -- the arguments still match the schema,
                                   re-checked here at the execution boundary
                                   rather than trusted from planning time
        Commit #3 plan          -- the unit of work, unchanged by execution
        Commit #4 permissions   -- this subject may invoke this tool

    What a tool actually *does* is a handler bound by the application via
    bind(): a bound method of a real project service, such as
    LLMNotebookAnalysisService.summary. Bindings deliberately live here and
    not in the registry, so Commit #1's invariant -- a registry that only
    catalogs and never executes -- still holds.

    Execution is bounded by construction. The model chooses a tool *name*
    and arguments; it never supplies a callable. A name only runs if it is
    registered, enabled, bound by the application, authorized for the
    subject, and carries schema-valid arguments. There is no path from
    model output to a shell, an eval, or an unbound callable.
    """

    def __init__(
        self,
        registry: LLMToolRegistryService,
        permission_service: LLMToolPermissionService,
        validation_service: LLMToolValidationService = None,
    ):
        self._registry = registry
        self._permission_service = permission_service
        self._validation_service = validation_service or LLMToolValidationService(registry)
        self._handlers = {}
        self._executions = {}
        self._execution_counter = 0

    def bind(self, tool_name: str, handler):
        """Bind a registered tool name to the real callable that implements it.

        Raises:
            UnknownToolError: If tool_name is not in the Commit #1 registry
            InvalidToolHandlerError: If handler is not callable, or is a
                code/shell execution primitive
        """
        # A handler may only ever be attached to a tool that already exists.
        self._registry.get(tool_name)

        if not callable(handler):
            raise InvalidToolHandlerError(
                f"handler for {tool_name!r} must be callable, got {type(handler).__name__}"
            )

        name = getattr(handler, "__name__", "")
        module = getattr(handler, "__module__", "") or ""
        if name in _FORBIDDEN_HANDLERS or module.split(".")[0] in _FORBIDDEN_HANDLER_MODULES:
            raise InvalidToolHandlerError(
                f"refusing to bind {module}.{name} as a tool: arbitrary code or "
                "shell execution is never a tool"
            )

        self._handlers[tool_name] = handler
        return handler

    def _record(
        self, plan_id, tool_name, status, result, error, started_at
    ) -> LLMToolExecution:
        self._execution_counter += 1
        execution = LLMToolExecution(
            execution_id=f"tool-execution-{self._execution_counter}",
            plan_id=plan_id,
            tool_name=tool_name,
            status=status,
            result=result,
            error=None if error is None else _redact(str(error)),
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
        self._executions[execution.execution_id] = execution
        return execution

    def execute(self, plan, subject) -> LLMToolExecution:
        """Run one plan on behalf of one subject, recording the outcome.

        Never raises for a refused or failing call -- every attempt becomes
        an LLMToolExecution whose status says what happened. Only a caller
        error (something that is not a plan) raises.
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise TypeError(
                f"Cannot execute something that is not an LLMToolInvocationPlan: {plan!r}."
            )

        started_at = datetime.now(timezone.utc)
        tool_name = plan.tool_name

        # 1. The tool must exist and be enabled. Commit #1's own gate.
        try:
            self._registry.get_invocable(tool_name)
        except UnknownToolError:
            return self._record(
                plan.plan_id, tool_name, REJECTED, None,
                f"tool {tool_name!r} is not registered", started_at,
            )
        except DisabledToolError:
            return self._record(
                plan.plan_id, tool_name, REJECTED, None,
                f"tool {tool_name!r} is disabled and cannot be invoked", started_at,
            )

        # 2. Authorization happens before execution -- Commit #4's rule. It
        #    also re-checks that the plan is READY and still valid.
        authorization = self._permission_service.authorize(plan, subject)
        if not authorization.allowed:
            return self._record(
                plan.plan_id, tool_name, DENIED, None, authorization.reason, started_at
            )

        # 3. Revalidate the arguments here, at the execution boundary, rather
        #    than trusting the verdict reached when the plan was made -- a
        #    definition can have changed in between.
        try:
            errors = self._validation_service.errors(tool_name, plan.arguments)
        except (UnknownToolError, DisabledToolError, InvalidToolDefinitionError) as exc:
            return self._record(
                plan.plan_id, tool_name, REJECTED, None,
                f"tool {tool_name!r} is not invocable: {exc}", started_at,
            )

        if errors:
            summary = "; ".join(
                f"{error.field or '<arguments>'} ({error.rule}): {error.message}"
                for error in errors
            )
            return self._record(
                plan.plan_id, tool_name, REJECTED, None,
                f"arguments failed revalidation: {summary}", started_at,
            )

        # 4. A registered tool with no bound handler has nothing to run. It is
        #    refused rather than improvised.
        handler = self._handlers.get(tool_name)
        if handler is None:
            return self._record(
                plan.plan_id, tool_name, REJECTED, None,
                f"tool {tool_name!r} has no bound handler", started_at,
            )

        # 5. Invoke the real service. Arguments are schema-validated, so every
        #    key is a property the tool declared.
        try:
            result = handler(**plan.arguments)
        except Exception as exc:
            # str(exc) only -- never a traceback, whose frames carry locals.
            detail = _redact(str(exc)) or exc.__class__.__name__
            return self._record(
                plan.plan_id, tool_name, FAILED, None,
                f"{exc.__class__.__name__}: {detail}", started_at,
            )

        return self._record(
            plan.plan_id, tool_name, SUCCEEDED, result, None, started_at
        )

    def _get(self, execution_id: str) -> LLMToolExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

    def get(self, execution_id: str) -> LLMToolExecution:
        return self._get(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def result(self, execution_id: str):
        """The value the tool returned.

        Raises:
            UnknownExecutionError: If execution_id was never recorded
            ExecutionNotSucceededError: If that execution did not succeed
        """
        execution = self._get(execution_id)
        if execution.status != SUCCEEDED:
            raise ExecutionNotSucceededError(
                f"execution {execution_id!r} is {execution.status}, not {SUCCEEDED}: "
                f"{execution.error}"
            )
        return execution.result

    def executions(self, status: str = None) -> list:
        recorded = list(self._executions.values())
        if status is not None:
            recorded = [execution for execution in recorded if execution.status == status]
        return recorded
