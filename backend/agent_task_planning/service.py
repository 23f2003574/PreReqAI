import json
from datetime import datetime, timezone

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.llm.tools import DisabledToolError, LLMToolRegistryService, UnknownToolError

from .models import READY, REJECTED, LLMAgentPlan, LLMAgentPlanStep

AGENT_TASK_PLANNING_SYSTEM_PROMPT = (
    "You are an agent task-planning assistant. You are given a user task, "
    "optional supporting context, and the list of tools this project "
    "actually exposes. Break the task into a sequence of steps that could "
    "be carried out using only those tools -- never invent a tool that "
    "isn't listed. Respond with ONLY a single JSON object -- no prose, no "
    "markdown fencing -- of the form {\"steps\": [...]}. Each entry in "
    "'steps' must be an object with: 'action' (a short human-readable "
    "description of what the step does), 'tool' (the exact name of one of "
    "the listed tools), 'arguments' (an object of arguments for that "
    "tool; use {} if none are needed), and 'depends_on' (a list of "
    "zero-based indices, into this same 'steps' list, of steps that must "
    "complete before this one; use [] if the step has no dependencies). "
    "This is a plan only -- it is never executed."
)


class MalformedAgentPlanResponseError(ValueError):
    """Raised when the LLM's task-plan response isn't well-formed."""


class UnknownAgentPlanError(KeyError):
    """Raised when validate()/preview()/get() is called for a plan_id that was never produced."""


def _parse_response(raw_content: str) -> list:
    """Structural validation of the raw LLM response. Returns the raw step dicts.

    Never inspects tool names or dependency targets against anything -- that
    is create()'s job, once step_ids exist to check dependencies against.
    This only enforces that the response is a JSON object shaped the way the
    system prompt asked for.
    """
    try:
        parsed = json.loads(raw_content)
    except (TypeError, ValueError) as exc:
        raise MalformedAgentPlanResponseError(f"LLM response is not valid JSON: {exc}")

    if not isinstance(parsed, dict) or not isinstance(parsed.get("steps"), list) or not parsed["steps"]:
        raise MalformedAgentPlanResponseError(
            "LLM response must be a JSON object with a non-empty 'steps' list"
        )

    steps = parsed["steps"]
    for step in steps:
        if not isinstance(step, dict):
            raise MalformedAgentPlanResponseError("each step must be an object")

        for key in ("action", "tool"):
            if not isinstance(step.get(key), str) or not step[key].strip():
                raise MalformedAgentPlanResponseError(f"step missing a non-empty {key!r}")

        if "arguments" in step and not isinstance(step["arguments"], dict):
            raise MalformedAgentPlanResponseError("step 'arguments' must be an object")

        depends_on = step.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(d, int) for d in depends_on):
            raise MalformedAgentPlanResponseError(
                "step 'depends_on' must be a list of integer step indices"
            )

    return steps


def _cyclic_step_ids(step_ids: list, edges: dict) -> set:
    """step_ids that participate in a dependency cycle, via depends_on edges.

    edges maps a step_id to the step_ids it depends on (only ones that
    resolved to a real step -- an unknown dependency is reported separately
    and never joins this graph). A step referencing its own id is treated as
    a one-node cycle.
    """
    color = {}
    cyclic = set()

    def visit(node, stack):
        color[node] = "visiting"
        stack.append(node)
        for dep in edges.get(node, ()):
            if color.get(dep) == "visiting":
                start = stack.index(dep)
                cyclic.update(stack[start:])
            elif dep not in color:
                visit(dep, stack)
        stack.pop()
        color[node] = "done"

    for step_id in step_ids:
        if step_id not in color:
            visit(step_id, [])

    return cyclic


class LLMAgentPlanningService:
    """Turns one user task into a structured, reviewable multi-step LLMAgentPlan.

    Reuses the existing backend.llm.orchestration.LLMRequestOrchestrationService
    to ask the model for a plan and backend.llm.context.LLMContextService to
    build the request context -- the same pipeline every other planning
    service in this project uses -- and the existing
    backend.llm.tools.LLMToolRegistryService as the sole source of what
    capabilities actually exist. No second agent framework is introduced:
    a step is only ever a reference to an already-registered tool, checked
    the same way backend.llm.tool_invocation checks a single tool call.

    create() is the only place an LLM is called. validate() and preview()
    are entirely deterministic: they re-read the registry and the
    already-recorded plan, and never make a request or run a tool. Nothing
    in this service has a dispatch surface -- it produces and inspects
    proposals only.
    """

    def __init__(
        self,
        registry: LLMToolRegistryService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._registry = registry
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="agent_task_planning", required_capabilities=["chat"]
        )
        self._plans = {}
        self._request_counter = 0
        self._plan_counter = 0

    def _available_tools(self) -> list:
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in self._registry.list(enabled_only=True)
        ]

    @staticmethod
    def _build_prompt(task: str, context: dict, available_tools: list) -> str:
        payload = {
            "task": task,
            "context": context or {},
            "available_tools": available_tools,
        }
        return json.dumps(payload)

    def _check_tool(self, tool_name: str) -> list:
        try:
            self._registry.get_invocable(tool_name)
        except UnknownToolError:
            return [f"tool {tool_name!r} is not registered"]
        except DisabledToolError:
            return [f"tool {tool_name!r} is disabled and cannot be invoked"]
        return []

    def create(self, task: str, context: dict = None) -> LLMAgentPlan:
        """Ask the model to break `task` into steps, then validate each one.

        Never executes a tool: every step is checked against the registry's
        existence/enabled gate only, exactly as backend.llm.tool_invocation
        checks a single call. A step naming an unknown or disabled tool, or
        an unresolvable dependency, is REJECTED but still recorded, so a
        reviewer can see exactly what was proposed and why it can't run.
        """
        if not task or not isinstance(task, str):
            raise ValueError("task is required")

        if context is not None and not isinstance(context, dict):
            raise ValueError("context must be a dict when given")

        self._request_counter += 1
        request_id = f"agent-plan-{self._request_counter}"

        self._context_service.create(request_id, system=AGENT_TASK_PLANNING_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(task, context, self._available_tools()),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedAgentPlanResponseError(f"LLM request failed: {decision.reason}")

        raw_steps = _parse_response(response.content)

        step_ids = [f"step-{index + 1}" for index in range(len(raw_steps))]
        edges = {}
        per_step_errors = []

        for index, (step_id, raw) in enumerate(zip(step_ids, raw_steps)):
            errors = list(self._check_tool(raw["tool"]))

            resolved_deps = []
            for dep_index in raw.get("depends_on", []):
                if dep_index == index or not (0 <= dep_index < len(raw_steps)):
                    errors.append(f"depends_on references an invalid step index {dep_index!r}")
                    continue
                resolved_deps.append(step_ids[dep_index])

            edges[step_id] = resolved_deps
            per_step_errors.append(errors)

        cyclic = _cyclic_step_ids(step_ids, edges)

        steps = []
        for index, (step_id, raw) in enumerate(zip(step_ids, raw_steps)):
            errors = list(per_step_errors[index])
            if step_id in cyclic:
                errors.append("depends_on forms a circular dependency")

            steps.append(
                LLMAgentPlanStep(
                    step_id=step_id,
                    action=raw["action"],
                    tool_name=raw["tool"],
                    arguments=dict(raw.get("arguments") or {}),
                    depends_on=list(edges[step_id]),
                    status=REJECTED if errors else READY,
                    errors=errors,
                )
            )

        self._plan_counter += 1
        plan = LLMAgentPlan(
            plan_id=f"agent-plan-{self._plan_counter}",
            task=task,
            steps=steps,
            status=READY if all(step.status == READY for step in steps) else REJECTED,
            created_at=datetime.now(timezone.utc),
        )
        self._plans[plan.plan_id] = plan
        return plan

    def _get(self, plan_id: str) -> LLMAgentPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise UnknownAgentPlanError(plan_id)

    def get(self, plan_id: str) -> LLMAgentPlan:
        return self._get(plan_id)

    def validate(self, plan_id: str) -> bool:
        """Re-check a recorded plan against the registry as it stands now.

        Deliberately re-runs the tool-availability check rather than
        trusting the stored status: a tool disabled after planning must
        make a previously READY plan invalid. Never mutates the plan and
        never executes anything.
        """
        plan = self._get(plan_id)
        if plan.status != READY:
            return False

        return all(not self._check_tool(step.tool_name) for step in plan.steps)

    def preview(self, plan_id: str) -> list:
        """Human-readable lines describing what the plan would do. Runs nothing."""
        plan = self._get(plan_id)

        lines = []
        for step in plan.steps:
            if step.status != READY:
                lines.append(f"REJECTED {step.step_id}: {step.action} ({'; '.join(step.errors)})")
                continue

            suffix = f" after {', '.join(step.depends_on)}" if step.depends_on else ""
            lines.append(f"{step.step_id}: {step.action} via {step.tool_name}{suffix}")
        return lines
