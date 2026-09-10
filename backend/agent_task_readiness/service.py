from backend.agent_policy_engine import LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement, PolicyEvaluationFailedError, is_blocking
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_lifecycle import RUNNING, LLMAgentTaskLifecycleService, UnknownAgentTaskError
from backend.agent_task_planning import LLMAgentPlanningService, UnknownAgentPlanError
from backend.agent_task_state_validation import LLMAgentTaskStateValidator

from .models import AgentTaskReadinessCheck, AgentTaskReadinessResult


class LLMAgentTaskReadinessService:
    """Read-only readiness gate: is task_id actually allowed to enter
    execution right now. Composes Commit #1-#3 plus this repository's
    own existing planning/context/policy interfaces into one fixed
    pipeline -- never a second lifecycle, history, validation, planning,
    context, or policy engine, and never anything that executes,
    schedules, or repairs task_id itself.

    check() always runs every applicable check and collects every
    blocking reason, rather than stopping at the first one (Rule:
    "report every blocking reason instead of stopping at the first
    failure") -- the same "collect everything, don't fail fast"
    reporting discipline backend.agent_risk_profile_validation.
    LLMAgentRiskProfileValidator already uses over Commit #1's own
    fail-fast create()/update(). A missing task_id is the sole
    exception: nothing else about a task that does not exist can be
    inspected at all, so check() short-circuits there with a single
    failed "task_exists" check.

    Fixed checks, run for every task:
      - task_exists: Commit #1's own LLMAgentTaskLifecycleService.get()
      - lifecycle_state: the task's own current_state must actually
        permit entering RUNNING -- Commit #1's own can_transition()
        (Rule: "use one authoritative transition definition", carried
        over from Commit #3), excluding the trivial RUNNING->RUNNING
        self-transition (a task already running is not "ready to
        enter" execution, it is already in it)
      - task_record: Commit #3's own LLMAgentTaskStateValidator.
        validate() -- malformed/inconsistent state, missing required
        identity fields, an unsound definition; its own warnings are
        carried through as this result's warnings, never as blockers
      - policy: backend.agent_policy_enforcement.LLMAgentPolicyEnforcement.
        enforce() against a generic {scope_id, agent_id, task_id,
        objective, action="agent_task_execution"} action_context, using
        that module's own is_blocking() -- so, exactly as at every
        other real enforcement boundary in this repository, "no
        applicable policy" never itself blocks a task, only an actual
        matched DENY rule does. A genuine evaluation failure (a
        misconfigured resolver, and never an ordinary DENY) fails
        closed, as a blocking reason -- the same "unknown must never
        silently become allowed" discipline enforce() itself documents.

    Conditional checks, run only when task_id's own AgentTask.definition
    (Commit #1's caller-supplied, opaque-to-Commit-#1 dict) names them --
    reading well-known keys out of it is this service's own business,
    never Commit #1's:
      - plan: only when definition names a "plan_id" *and* a
        planning_service was actually supplied to __init__ (it has no
        usable zero-argument default -- see __init__'s own docstring);
        with both present, the referenced backend.agent_task_planning.
        LLMAgentPlan must exist and its own validate() must report True.
        This only ever covers a *plan's own internal* step graph: a
        plan's validate()/create() already guarantee every step's
        depends_on references a real step_id with no cycle (see that
        module's own LLMAgentPlan docstring); backend.
        agent_dependency_resolution is scoped to steps of an
        *already-started* execution (it takes an execution_id, only
        created once a task is already RUNNING), so it has nothing to
        answer before that point and is not reused here.
      - dependencies: only when a dependency_service was actually
        supplied to __init__ -- Commit #5's own backend.
        agent_task_dependencies.LLMAgentTaskDependencyService.
        check_dependencies(task_id) is called and consumed directly
        (Rule: "existing task readiness should be able to consume this
        result rather than duplicate dependency checks" -- this is the
        *task-to-task* prerequisite graph Commit #5 introduces, a
        completely different thing from one plan's own internal step
        graph immediately above). Every pending/failed/blocked
        dependency_task_id in the result becomes its own blocking
        reason; an unsatisfied result is never collapsed to one vague
        message, so a caller can see exactly which prerequisite(s) are
        still outstanding.
      - context: only when definition sets "requires_context" truthy --
        backend.agent_task_context.LLMAgentTaskContextService.get(task_id)
        must succeed (the same task_id joins both records, exactly as
        every other module in this repository keys its own records off
        the caller's shared task_id/agent_id/scope_id). Deliberately
        stops at *availability*, not the deeper integrity check backend.
        agent_task_context_integrity.LLMAgentTaskContextIntegrityService.
        validate() performs: that method's own signature takes an
        already-built AgentContextPackage, which only exists after
        running the full resolution/budgeting/packaging pipeline --
        running that pipeline here, before a task is ever actually
        scheduled, would mean this read-only gate quietly building and
        discarding real execution machinery, exactly what Rule "do not
        invent a new execution/runtime system" rules out. An available-
        but-empty context (no relevant_context entries yet) is reported
        as a warning, never a blocker -- availability is what Rule
        requires; richness is advisory.
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        context_service: LLMAgentTaskContextService = None,
        planning_service: LLMAgentPlanningService = None,
        policy_enforcement: LLMAgentPolicyEnforcement = None,
        dependency_service: LLMAgentTaskDependencyService = None,
    ):
        """
        Args:
            lifecycle_service: The exact Commit #1
                LLMAgentTaskLifecycleService instance holding the tasks
                this readiness service will be asked about -- required,
                never defaulted, since a fresh instance's in-memory
                store could never hold any real task
            context_service: Defaults to a fresh
                backend.agent_task_context.LLMAgentTaskContextService;
                pass the real instance holding a task's context for the
                "context" check to ever find anything
            planning_service: No usable default (see this class's own
                docstring); pass the real
                backend.agent_task_planning.LLMAgentPlanningService
                instance holding a task's plan to enable the "plan"
                check at all -- left None, that check is always skipped
            policy_enforcement: Defaults to a fresh
                backend.agent_policy_enforcement.LLMAgentPolicyEnforcement
                over a fresh, empty policy store (so "policy" always
                passes unless a caller supplies the real, populated one)
            dependency_service: No default (mirrors planning_service --
                it must be the exact instance holding a task's recorded
                dependency edges); left None, the "dependencies" check
                is always skipped
        """
        self._lifecycle_service = lifecycle_service
        self._context_service = context_service if context_service is not None else LLMAgentTaskContextService()
        # Unlike context_service/policy_enforcement, LLMAgentPlanningService
        # has no meaningful zero-argument default: its own constructor
        # requires a real LLMToolRegistryService/orchestration_service/
        # context_service (create() calls an LLM through them), and it is
        # the same in-memory, per-instance _plans dict a plan was actually
        # created against -- there is no "fresh" instance that could ever
        # resolve a real plan_id. Left None unless a caller supplies the
        # exact instance holding their own plans; the plan check (see
        # _check_plan()) is simply skipped, not faked, when it is None.
        self._planning_service = planning_service
        self._policy_enforcement = (
            policy_enforcement
            if policy_enforcement is not None
            else LLMAgentPolicyEnforcement(LLMAgentPolicyResolver(LLMAgentPolicyService()))
        )
        self._dependency_service = dependency_service

    def is_ready(self, task_id: str) -> bool:
        """Shorthand for check(task_id).ready."""
        return self.check(task_id).ready

    def check(self, task_id: str) -> AgentTaskReadinessResult:
        """Every applicable readiness check for task_id, in one
        deterministic pass. Never mutates, schedules, executes, or
        repairs task_id or anything it references -- every collaborator
        called here is itself read-only (see this class's own
        docstring)."""
        checks = []
        blocking_reasons = []
        warnings = []

        try:
            task = self._lifecycle_service.get(task_id)
        except UnknownAgentTaskError:
            reason = f"task {task_id!r} does not exist"
            checks.append(AgentTaskReadinessCheck(name="task_exists", passed=False, detail=reason))
            return AgentTaskReadinessResult(
                ready=False, task_id=task_id, blocking_reasons=[reason], warnings=[], checks=checks
            )
        checks.append(AgentTaskReadinessCheck(name="task_exists", passed=True))

        self._check_lifecycle_state(task, checks, blocking_reasons)
        self._check_task_record(task, checks, blocking_reasons, warnings)
        self._check_plan(task, checks, blocking_reasons)
        self._check_dependencies(task, checks, blocking_reasons)
        self._check_context(task, checks, blocking_reasons, warnings)
        self._check_policy(task, checks, blocking_reasons)

        return AgentTaskReadinessResult(
            ready=not blocking_reasons,
            task_id=task_id,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            checks=checks,
        )

    @staticmethod
    def _check_lifecycle_state(task, checks, blocking_reasons) -> None:
        permits_execution = task.current_state != RUNNING and LLMAgentTaskLifecycleService.can_transition(
            task.current_state, RUNNING
        )
        if permits_execution:
            checks.append(AgentTaskReadinessCheck(name="lifecycle_state", passed=True))
            return

        reason = f"lifecycle state {task.current_state!r} does not permit entering execution"
        blocking_reasons.append(reason)
        checks.append(AgentTaskReadinessCheck(name="lifecycle_state", passed=False, detail=reason))

    @staticmethod
    def _check_task_record(task, checks, blocking_reasons, warnings) -> None:
        result = LLMAgentTaskStateValidator.validate(task)
        warnings.extend(f"task record: {warning}" for warning in result.warnings)

        if result.valid:
            checks.append(AgentTaskReadinessCheck(name="task_record", passed=True))
            return

        for error in result.errors:
            reason = f"task record invalid: {error}"
            blocking_reasons.append(reason)
        checks.append(
            AgentTaskReadinessCheck(name="task_record", passed=False, detail="; ".join(result.errors))
        )

    def _check_plan(self, task, checks, blocking_reasons) -> None:
        plan_id = task.definition.get("plan_id") if isinstance(task.definition, dict) else None
        if not plan_id or self._planning_service is None:
            return

        try:
            self._planning_service.get(plan_id)
        except UnknownAgentPlanError:
            reason = f"referenced plan {plan_id!r} does not exist"
            blocking_reasons.append(reason)
            checks.append(AgentTaskReadinessCheck(name="plan", passed=False, detail=reason))
            return

        if self._planning_service.validate(plan_id):
            checks.append(AgentTaskReadinessCheck(name="plan", passed=True))
            return

        reason = f"plan {plan_id!r} is not valid (a referenced tool may be missing/disabled, or a step is REJECTED)"
        blocking_reasons.append(reason)
        checks.append(AgentTaskReadinessCheck(name="plan", passed=False, detail=reason))

    def _check_dependencies(self, task, checks, blocking_reasons) -> None:
        if self._dependency_service is None:
            return

        result = self._dependency_service.check_dependencies(task.task_id)
        if result.satisfied:
            checks.append(AgentTaskReadinessCheck(name="dependencies", passed=True))
            return

        reasons = (
            [f"dependency {dep!r} has not completed yet" for dep in result.pending]
            + [f"dependency {dep!r} failed or was cancelled" for dep in result.failed]
            + [f"dependency {dep!r} is missing or part of a dependency cycle" for dep in result.blocked]
        )
        blocking_reasons.extend(reasons)
        checks.append(AgentTaskReadinessCheck(name="dependencies", passed=False, detail="; ".join(reasons)))

    def _check_context(self, task, checks, blocking_reasons, warnings) -> None:
        requires_context = isinstance(task.definition, dict) and task.definition.get("requires_context")
        if not requires_context:
            return

        try:
            context = self._context_service.get(task.task_id)
        except UnknownTaskContextError:
            reason = f"required task context for {task.task_id!r} is not available"
            blocking_reasons.append(reason)
            checks.append(AgentTaskReadinessCheck(name="context", passed=False, detail=reason))
            return

        checks.append(AgentTaskReadinessCheck(name="context", passed=True))
        if not context.relevant_context:
            # Advisory only: the context record exists (Rule's own
            # "available" bar is met), but carries no actual content yet
            # -- worth surfacing, never blocking on its own.
            warnings.append(f"task context for {task.task_id!r} has no relevant_context entries")

    def _check_policy(self, task, checks, blocking_reasons) -> None:
        action_context = {
            "scope_id": task.scope_id,
            "agent_id": task.agent_id,
            "task_id": task.task_id,
            "objective": task.objective,
            "action": "agent_task_execution",
        }

        try:
            decision = self._policy_enforcement.enforce(action_context)
        except PolicyEvaluationFailedError as error:
            reason = f"policy evaluation failed: {error}"
            blocking_reasons.append(reason)
            checks.append(AgentTaskReadinessCheck(name="policy", passed=False, detail=reason))
            return

        if not is_blocking(decision):
            checks.append(AgentTaskReadinessCheck(name="policy", passed=True))
            return

        reason = f"policy denies task execution: {'; '.join(decision.reasons) if decision.reasons else 'matched deny rule'}"
        blocking_reasons.append(reason)
        checks.append(AgentTaskReadinessCheck(name="policy", passed=False, detail=reason))
