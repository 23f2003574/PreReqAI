import copy
import json

from ..tool_validation import LLMToolValidationError, LLMToolValidationService
from ..tools import (
    DisabledToolError,
    InvalidToolDefinitionError,
    LLMToolRegistryService,
    UnknownToolError,
)
from .models import (
    DISABLED_TOOL,
    MALFORMED_SCHEMA,
    READY,
    REJECTED,
    UNKNOWN_TOOL,
    LLMToolInvocationPlan,
)


class MalformedToolCallError(ValueError):
    """Raised when a tool call has no usable tool name to plan against.

    A call that names a tool can always be recorded -- as READY or REJECTED.
    A call that isn't an object, isn't parseable JSON, or names nothing has
    nothing to plan for at all, so it is refused outright rather than
    recorded.
    """


class UnknownToolPlanError(KeyError):
    """Raised when validate()/preview()/get() is called for an unknown plan_id."""


def normalize_tool_call(tool_call) -> dict:
    """Accept a tool-call dict, or the JSON string an LLMResponse carries.

    Providers hand back tool calls as {"name": ..., "arguments": {...}}
    (optionally with an "id" and the model's own "rationale"). The same
    object often reaches a caller as JSON text in LLMResponse.content,
    so that form is accepted too -- LLMResponse itself is left alone
    rather than grown a tool_calls field it does not have.
    """
    if isinstance(tool_call, str):
        try:
            tool_call = json.loads(tool_call)
        except (TypeError, ValueError) as exc:
            raise MalformedToolCallError(f"tool call is not valid JSON: {exc}")

    if not isinstance(tool_call, dict):
        raise MalformedToolCallError(
            f"tool call must be an object, got {type(tool_call).__name__}"
        )

    name = tool_call.get("name")
    if not name or not isinstance(name, str):
        raise MalformedToolCallError("tool call must name a tool")

    if "arguments" in tool_call and not isinstance(tool_call["arguments"], (dict, str)):
        raise MalformedToolCallError(
            f"tool call arguments must be an object, got "
            f"{type(tool_call['arguments']).__name__}"
        )

    return tool_call


def extract_tool_call_arguments(tool_call: dict):
    """Pull the argument payload out of a call, JSON-decoding it if needed.

    Some providers nest arguments as a JSON string. A string that will
    not decode is returned as-is so schema validation reports it as a
    non-object payload rather than this method raising -- the call
    itself is well-formed, its arguments simply are not.
    """
    arguments = tool_call.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (TypeError, ValueError):
            return arguments
    return arguments


class LLMToolInvocationService:
    """Turns one LLM-produced tool call into a validated execution plan (Commit #3).

    Reuses Commit #1's LLMToolRegistryService for what exists and what is
    enabled, and Commit #2's LLMToolValidationService for whether the
    model's arguments match the tool's declared schema -- this service adds
    no validation rules of its own, it only records the outcome as a plan.

    Planning is entirely deterministic: no LLM call is made here. The tool
    call being planned has already been produced by the model, so converting
    it into a plan is a matter of checking it, not of asking for anything.

    Nothing here executes a tool. plan()/validate()/preview() read the
    registry, inspect an argument dict, and format strings; the service has
    no dispatch surface and never calls the capability a tool describes.
    """

    def __init__(
        self,
        registry: LLMToolRegistryService,
        validation_service: LLMToolValidationService = None,
    ):
        self._registry = registry
        self._validation_service = validation_service or LLMToolValidationService(registry)
        self._plans = {}
        self._plan_counter = 0

    def _rationale(self, tool_call: dict, tool_name: str, errors: list) -> str:
        """The model's own rationale when it gave one, else a stated fallback.

        Never asks an LLM for one -- a plan's rationale must describe the
        call that was actually made.
        """
        given = tool_call.get("rationale")
        if isinstance(given, str) and given.strip():
            return given.strip()

        if errors:
            return f"tool call to {tool_name!r} rejected: {len(errors)} validation error(s)"

        try:
            description = self._registry.get(tool_name).description
        except UnknownToolError:
            return f"tool call to {tool_name!r}"
        return f"tool call to {tool_name!r}: {description}"

    def _check(self, tool_name: str, arguments) -> list:
        """Every reason this call cannot proceed, as structured error entries.

        Delegates entirely to Commit #1's registry and Commit #2's validation
        service; the three conditions those raise for (unknown, disabled,
        malformed definition) are converted into error entries here, because
        a plan records why it was rejected rather than refusing to exist.
        """
        try:
            return self._validation_service.errors(tool_name, arguments)
        except UnknownToolError:
            return [
                LLMToolValidationError(
                    tool_name=tool_name,
                    field=None,
                    rule=UNKNOWN_TOOL,
                    value=None,
                    message=f"tool {tool_name!r} is not registered",
                )
            ]
        except DisabledToolError:
            return [
                LLMToolValidationError(
                    tool_name=tool_name,
                    field=None,
                    rule=DISABLED_TOOL,
                    value=None,
                    message=f"tool {tool_name!r} is disabled and cannot be invoked",
                )
            ]
        except InvalidToolDefinitionError as exc:
            return [
                LLMToolValidationError(
                    tool_name=tool_name,
                    field=None,
                    rule=MALFORMED_SCHEMA,
                    value=None,
                    message=f"tool {tool_name!r} has an unusable definition: {exc}",
                )
            ]

    def plan(self, tool_call) -> LLMToolInvocationPlan:
        """Record one tool call as a READY or REJECTED plan. Executes nothing."""
        tool_call = normalize_tool_call(tool_call)
        tool_name = tool_call["name"]
        arguments = extract_tool_call_arguments(tool_call)

        errors = self._check(tool_name, arguments)

        self._plan_counter += 1
        plan = LLMToolInvocationPlan(
            plan_id=f"tool-plan-{tool_name}-{self._plan_counter}",
            tool_name=tool_name,
            # Deep copies throughout: a caller mutating the dict it passed in
            # afterward must never reach into a recorded plan, and the
            # preserved call must stay exactly what the model produced.
            arguments=copy.deepcopy(arguments),
            rationale=self._rationale(tool_call, tool_name, errors),
            status=REJECTED if errors else READY,
            tool_call=copy.deepcopy(tool_call),
            errors=errors,
        )

        self._plans[plan.plan_id] = plan
        return plan

    def _get(self, plan_id: str) -> LLMToolInvocationPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise UnknownToolPlanError(plan_id)

    def get(self, plan_id: str) -> LLMToolInvocationPlan:
        return self._get(plan_id)

    def validate(self, plan_id: str) -> bool:
        """Re-check a recorded plan against the registry as it stands now.

        Deliberately re-runs the checks rather than trusting the stored
        status: a tool disabled, or a definition changed, after planning must
        make a previously READY plan fail. Never mutates the plan.
        """
        plan = self._get(plan_id)
        if plan.status != READY:
            return False
        return not self._check(plan.tool_name, plan.arguments)

    def preview(self, plan_id: str) -> list:
        """Human-readable lines describing what the plan would do. Runs nothing."""
        plan = self._get(plan_id)

        if plan.status != READY:
            lines = [f"REJECTED {plan.tool_name}"]
            lines.extend(
                f"  {error.field or '<arguments>'} ({error.rule}): {error.message}"
                for error in plan.errors
            )
            return lines

        lines = [f"CALL {plan.tool_name}"]
        lines.extend(f"  {field} = {value!r}" for field, value in plan.arguments.items())
        lines.append(f"  -- {plan.rationale}")
        return lines

    def plans(self, status: str = None) -> list:
        recorded = list(self._plans.values())
        if status is not None:
            recorded = [plan for plan in recorded if plan.status == status]
        return recorded
