from backend.agent_task_planning import cyclic_step_ids
from backend.llm.tool_invocation import READY as INVOCATION_READY
from backend.llm.tool_invocation import LLMToolInvocationPlan, LLMToolInvocationService
from backend.llm.tool_permissions import ANY_SUBJECT
from backend.llm.tools import DisabledToolError, LLMToolRegistryService, UnknownToolError

from .models import (
    DEPENDENCY_CYCLE,
    DISABLED_TOOL,
    INVALID_DEPENDENCY,
    PERMISSION_CONFLICT,
    UNKNOWN_TOOL,
    LLMAgentPlanFinding,
)


class LLMAgentPlanValidationService:
    """Validates a Commit #1 LLMAgentPlan against the project as it stands now.

    This is not a second planner: it never proposes, reorders, or repairs a
    step, and it introduces no new dependency-graph algorithm of its
    own -- validate_dependencies() reuses Commit #1's own cyclic_step_ids()
    to walk the same graph the same way. What this service adds beyond
    Commit #1 is re-checking against live state rather than the status a
    plan was created with (a tool disabled after planning must surface
    here even though the plan's own step.status still says READY), plus a
    dimension Commit #1 never checked at all: whether the tool a step
    names is actually invokable by anyone, via the existing
    backend.llm.tool_permissions.LLMToolPermissionService.

    A step's tool call is never invoked to check permission -- authorize()
    is asked about a synthetic backend.llm.tool_invocation.LLMToolInvocationPlan
    built from the step's own tool_name/arguments, the same value object
    Commit #4 of the tool-calling chain already authorizes against, so no
    second authorization model is introduced either.

    Every method here is a read: validate_steps(), validate_dependencies(),
    validate() and blocking() all recompute their answer from the plan and
    the registry/permission service as currently registered, and none of
    them execute a tool or mutate the plan.
    """

    def __init__(
        self,
        planning_service,
        registry: LLMToolRegistryService,
        permission_service=None,
        invocation_service: LLMToolInvocationService = None,
    ):
        """
        Args:
            planning_service: The Commit #1 LLMAgentPlanningService (or
                anything exposing its get()), the sole source of plans
            registry: The Commit #1 tool registry
            permission_service: Optional existing
                backend.llm.tool_permissions.LLMToolPermissionService. When
                omitted, validate()/blocking() skip permission checks
                entirely
            invocation_service: Optional existing
                backend.llm.tool_invocation.LLMToolInvocationService. Pass
                the *same* instance permission_service was built with (if
                any) -- the synthetic plan a permission check authorizes is
                built by calling this service's own plan(), so that
                permission_service's own re-validation of it (when it was
                given an invocation_service) resolves against a plan that
                genuinely exists there. When omitted, a bare plan is
                constructed directly instead, which is only safe when
                permission_service has no invocation_service of its own to
                re-validate against.
        """
        self._planning_service = planning_service
        self._registry = registry
        self._permission_service = permission_service
        self._invocation_service = invocation_service

    def _plan(self, plan_id: str):
        """Fetch the Commit #1 plan. Propagates its own UnknownAgentPlanError."""
        return self._planning_service.get(plan_id)

    def _tool_error(self, step) -> LLMAgentPlanFinding:
        """The one blocking finding for a step whose tool is unusable, or None."""
        try:
            self._registry.get_invocable(step.tool_name)
        except UnknownToolError:
            return LLMAgentPlanFinding(
                step_id=step.step_id,
                category=UNKNOWN_TOOL,
                message=f"tool {step.tool_name!r} is not registered",
                blocking=True,
            )
        except DisabledToolError:
            return LLMAgentPlanFinding(
                step_id=step.step_id,
                category=DISABLED_TOOL,
                message=f"tool {step.tool_name!r} is disabled and cannot be invoked",
                blocking=True,
            )
        return None

    def validate_steps(self, plan_id: str) -> list:
        """Every tool a step names must currently exist and be enabled."""
        plan = self._plan(plan_id)
        findings = []
        for step in plan.steps:
            finding = self._tool_error(step)
            if finding is not None:
                findings.append(finding)
        return findings

    def validate_dependencies(self, plan_id: str) -> list:
        """Every depends_on reference must name a real step, and no cycles."""
        plan = self._plan(plan_id)
        step_ids = [step.step_id for step in plan.steps]
        id_set = set(step_ids)
        edges = {step.step_id: list(step.depends_on) for step in plan.steps}

        findings = []
        for step in plan.steps:
            for dependency in step.depends_on:
                if dependency not in id_set:
                    findings.append(
                        LLMAgentPlanFinding(
                            step_id=step.step_id,
                            category=INVALID_DEPENDENCY,
                            message=f"depends on unknown step {dependency!r}",
                            blocking=True,
                        )
                    )

        for step_id in cyclic_step_ids(step_ids, edges):
            findings.append(
                LLMAgentPlanFinding(
                    step_id=step_id,
                    category=DEPENDENCY_CYCLE,
                    message="step participates in a circular dependency",
                    blocking=True,
                )
            )

        return findings

    def _validate_permissions(self, plan_id: str, subject) -> list:
        """Whether `subject` could invoke every step's tool, per the existing
        LLMToolPermissionService. Skipped entirely when no permission
        service was wired, and skipped per-step when the tool itself is
        already unusable -- that is validate_steps()'s finding to report,
        not a permission conflict.
        """
        if self._permission_service is None:
            return []

        plan = self._plan(plan_id)
        findings = []
        for step in plan.steps:
            if self._tool_error(step) is not None:
                continue

            if self._invocation_service is not None:
                synthetic_plan = self._invocation_service.plan(
                    {"name": step.tool_name, "arguments": step.arguments}
                )
            else:
                synthetic_plan = LLMToolInvocationPlan(
                    plan_id=f"{plan_id}-{step.step_id}",
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    rationale=step.action,
                    status=INVOCATION_READY,
                    tool_call={"name": step.tool_name, "arguments": step.arguments},
                    errors=[],
                )
            authorization = self._permission_service.authorize(synthetic_plan, subject)
            if not authorization.allowed:
                findings.append(
                    LLMAgentPlanFinding(
                        step_id=step.step_id,
                        category=PERMISSION_CONFLICT,
                        message=authorization.reason,
                        blocking=True,
                    )
                )
        return findings

    def validate(self, plan_id: str, subject: str = ANY_SUBJECT) -> list:
        """Every finding against `plan_id`: tools, dependencies, and permissions.

        `subject` defaults to ANY_SUBJECT so a plan's permission
        satisfiability can be checked as a property of the plan itself
        (is this tool usable by anyone at all); pass a specific subject to
        check whether that subject in particular could carry it out.
        """
        findings = []
        findings.extend(self.validate_steps(plan_id))
        findings.extend(self.validate_dependencies(plan_id))
        findings.extend(self._validate_permissions(plan_id, subject))
        return findings

    def blocking(self, plan_id: str, subject: str = ANY_SUBJECT) -> bool:
        """Whether `plan_id` has any blocking finding -- an invalid plan must
        never be handed to an executor."""
        return any(finding.blocking for finding in self.validate(plan_id, subject=subject))
