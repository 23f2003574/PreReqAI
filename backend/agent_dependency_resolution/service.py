from backend.agent_task_planning import cyclic_step_ids
from backend.llm.tool_execution import SUCCEEDED


class UnknownDependencyStepError(KeyError):
    """Raised when dependencies() names a step_id that is not part of the plan."""


class LLMAgentDependencyService:
    """Read-only view of which of a plan execution's steps can run right now.

    Not another workflow engine: this service holds no state of its own
    and runs nothing. It only reads Commit #1's plan (for each step's
    declared depends_on) and Commit #3's own execution records (for which
    steps have actually succeeded, failed, or never been attempted) and
    classifies each step as ready or blocked from that. Deciding to
    actually run a ready step, and everything that happens once it does,
    stays entirely Commit #3/#4's -- this service never calls execute_step()
    or anything beneath it.

    `execution_id` is resolved to a plan the same way Commits #5-#7 do:
    via Commit #4's plan_execution_service.get(execution_id).plan_id, when
    a plan_execution_service was given. Commit #3's own execute_step() has
    no such wrapper and works directly off plan_id, so a caller driving
    steps that way -- or resolving readiness before a Commit #4 execution
    has even been started -- may construct this service without one;
    execution_id is then taken to be the plan_id itself. dependencies()
    additionally takes execution_id (beyond the bare step_id the goal
    names) for the same reason every other method here does -- a step_id
    is only unique within one plan, and execution_id is what says which
    plan that is.

    A step is ready only when it has never been attempted and every step
    it depends on has SUCCEEDED. Once a step has any recorded outcome --
    SUCCEEDED or otherwise -- it never becomes ready again: a SUCCEEDED
    step is finished and excluded from both ready_steps() and
    blocked_steps() entirely, and any other outcome (FAILED, DENIED,
    REJECTED, TIMED_OUT, CANCELLED) blocks it for good, since retrying it
    would be autonomous replanning, out of scope here. A step named by a
    dependency cycle, or one whose depends_on names a step outside the
    plan altogether, is defensively treated as permanently blocked too --
    checked fresh here via Commit #1's own cyclic_step_ids(), independent
    of whether Commit #2 validation was ever run against this plan.
    """

    def __init__(self, planning_service, step_execution_service, plan_execution_service=None):
        self._planning_service = planning_service
        self._step_execution_service = step_execution_service
        self._plan_execution_service = plan_execution_service

    def _plan(self, execution_id: str):
        if self._plan_execution_service is not None:
            plan_id = self._plan_execution_service.get(execution_id).plan_id
        else:
            plan_id = execution_id
        return self._planning_service.get(plan_id)

    def _status_by_step(self, plan_id: str) -> dict:
        """The latest recorded status per step_id. Absent entirely means
        never attempted -- Commit #3's own executions(), in creation order,
        so a later re-attempt (were one ever recorded) would win."""
        status = {}
        for record in self._step_execution_service.executions(plan_id):
            status[record.step_id] = record.status
        return status

    @staticmethod
    def _unsafe_step_ids(plan) -> set:
        """step_ids that can never legitimately become ready: a dependency
        cycle, or a depends_on naming a step outside this plan entirely."""
        step_ids = {step.step_id for step in plan.steps}
        edges = {step.step_id: list(step.depends_on) for step in plan.steps}

        unsafe = {
            step.step_id for step in plan.steps
            if any(dependency not in step_ids for dependency in step.depends_on)
        }
        unsafe |= cyclic_step_ids([step.step_id for step in plan.steps], edges)
        return unsafe

    def _readiness(self, execution_id: str):
        """(ready step_ids, blocked step_ids), each in plan declaration order."""
        plan = self._plan(execution_id)
        status_by_step = self._status_by_step(plan.plan_id)
        unsafe = self._unsafe_step_ids(plan)

        ready, blocked = [], []
        for step in plan.steps:
            status = status_by_step.get(step.step_id)

            if status == SUCCEEDED:
                continue  # completed -- excluded from both lists

            if status is not None:
                blocked.append(step.step_id)  # already attempted, did not succeed
                continue

            if step.step_id in unsafe:
                blocked.append(step.step_id)
                continue

            if all(status_by_step.get(dependency) == SUCCEEDED for dependency in step.depends_on):
                ready.append(step.step_id)
            else:
                blocked.append(step.step_id)

        return ready, blocked

    def ready_steps(self, execution_id: str) -> list:
        ready, _blocked = self._readiness(execution_id)
        return ready

    def blocked_steps(self, execution_id: str) -> list:
        _ready, blocked = self._readiness(execution_id)
        return blocked

    def can_execute(self, execution_id: str, step_id: str) -> bool:
        return step_id in self.ready_steps(execution_id)

    def dependencies(self, execution_id: str, step_id: str) -> list:
        """The step_ids `step_id` declares in depends_on -- a pure reading
        of Commit #1's plan, unaffected by any execution state."""
        plan = self._plan(execution_id)
        for step in plan.steps:
            if step.step_id == step_id:
                return list(step.depends_on)
        raise UnknownDependencyStepError(step_id)
