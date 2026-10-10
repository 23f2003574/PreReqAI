from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
from backend.agent_task_dependency_impact import LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import STATES, LLMAgentTaskLifecycleService, UnknownAgentTaskError
from backend.agent_task_planning import cyclic_step_ids

from .models import DEPENDENCY_ADDED, DEPENDENCY_REMOVED, STATE_CHANGE, AgentTaskDependencyChangeImpact
from .views import EdgeOverrideDependencyStore, StateOverrideLifecycleView


class LLMAgentTaskDependencyChangeImpactService:
    """Explains exactly how one described task/dependency change would
    affect (or already affects) existing Commit #8 readiness plans and
    what a Commit #9 cache would need to invalidate for it -- without
    ever performing the change, or any real invalidation, itself.

    analyze_change() never mutates Commit #1/#5's real state: for the
    "post-change" half of every comparison it builds a temporary,
    read-only override view (.views.StateOverrideLifecycleView for a
    state change, .views.EdgeOverrideDependencyStore for a dependency
    change) and hands that to a fresh Commit #6
    LLMAgentTaskDependencyResolver / Commit #8
    LLMAgentTaskDependencyReadinessService pair -- the exact same
    classes every other commit in this series already uses, never a
    second resolver or a second readiness engine (Rule: "reuse existing
    resolver/cache models" / "do not create another dependency graph or
    cache"). The "pre-change" half is built the identical way, with the
    override set to the *other* side of the described change -- this
    makes every comparison entirely self-contained, from the caller's
    own description alone, regardless of whether the real mutation has
    already happened, is about to, or never will.

    Downstream discovery (step 1: "resolve downstream impact using the
    existing dependency graph") is Commit #7's own
    LLMAgentTaskDependencyImpactService.analyze(task_id).
    transitive_dependents, called once against the real, current graph
    -- correct regardless of which hypothetical is being evaluated,
    since who depends on task_id never changes just because task_id's
    own state or own dependencies did (Rule: "do not duplicate graph
    traversal").

    Every candidate task's pre/post Commit #8 AgentTaskDependencyReadinessPlan
    is compared field-for-field (dataclass equality) to decide
    affected_tasks/newly_blocked_tasks/newly_ready_tasks/unchanged_tasks
    (steps 2-3). invalidated_cache_entries (step 4) is always the whole
    candidate set (task_id plus every transitive dependent) -- exactly
    Commit #10's own actual, deliberately conservative invalidation
    footprint (its on_task_state_changed()/on_dependency_changed() both
    invalidate task_id plus every transitive dependent unconditionally,
    never only the ones a full recompute would show as truly different)
    -- so this field always answers "what would a correct cache
    invalidate", not "what would a perfectly precise cache invalidate".
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        dependency_service: LLMAgentTaskDependencyService,
        dependency_impact_service: LLMAgentTaskDependencyImpactService,
    ):
        self._lifecycle_service = lifecycle_service
        self._dependency_service = dependency_service
        self._dependency_impact_service = dependency_impact_service

    def analyze_change(
        self,
        task_id: str,
        change_type: str,
        dependency_task_id: str = None,
        old_state: str = None,
        new_state: str = None,
    ) -> AgentTaskDependencyChangeImpact:
        """Explain the impact of one described change to task_id.

        Raises:
            UnknownAgentTaskError: If task_id itself was never created
                via Commit #1 -- the same "a missing root task_id is a
                caller error, not an unresolved analysis" convention
                every other service in this series already uses
                (Commit #6/#7/#8's own resolve()/analyze()/build_plan()).
                Every *other* way a change cannot be evaluated (an
                unrecognized change_type, an illegal hypothetical
                transition, a missing/self-referential
                dependency_task_id, a hypothetical edge that would
                create a cycle, ...) is reported via the returned
                result's own unresolved_reason instead, never raised.
        """
        self._lifecycle_service.get(task_id)

        if change_type == STATE_CHANGE:
            return self._analyze_state_change(task_id, old_state, new_state)
        if change_type in (DEPENDENCY_ADDED, DEPENDENCY_REMOVED):
            return self._analyze_dependency_change(task_id, change_type, dependency_task_id)

        return self._unresolved(task_id, f"unknown change_type {change_type!r}")

    def _analyze_state_change(self, task_id, old_state, new_state):
        if old_state not in STATES or new_state not in STATES:
            return self._unresolved(task_id, "old_state and new_state must both be valid lifecycle states")
        if old_state == new_state:
            return self._unresolved(task_id, f"old_state and new_state are both {old_state!r}; not a real change")
        if not LLMAgentTaskLifecycleService.can_transition(old_state, new_state):
            return self._unresolved(task_id, f"{old_state!r} -> {new_state!r} is not a legal transition")

        pre_lifecycle = StateOverrideLifecycleView(self._lifecycle_service, task_id, old_state)
        post_lifecycle = StateOverrideLifecycleView(self._lifecycle_service, task_id, new_state)
        description = f"task {task_id!r}: {old_state!r} -> {new_state!r}"
        return self._compare(
            task_id, pre_lifecycle, self._dependency_service, post_lifecycle, self._dependency_service, description
        )

    def _analyze_dependency_change(self, task_id, change_type, dependency_task_id):
        if not dependency_task_id or not isinstance(dependency_task_id, str):
            return self._unresolved(task_id, "dependency_task_id is required for a dependency change")
        if dependency_task_id == task_id:
            return self._unresolved(task_id, "a task cannot depend on itself")
        try:
            self._lifecycle_service.get(dependency_task_id)
        except UnknownAgentTaskError:
            return self._unresolved(task_id, f"dependency_task_id {dependency_task_id!r} does not exist")

        edge = TaskDependency(task_id=task_id, dependency_task_id=dependency_task_id)
        edge_key = (task_id, dependency_task_id)
        if change_type == DEPENDENCY_ADDED:
            pre_store = EdgeOverrideDependencyStore(self._dependency_service.store, remove_edge=edge_key)
            post_store = EdgeOverrideDependencyStore(self._dependency_service.store, add_edge=edge)
        else:
            pre_store = EdgeOverrideDependencyStore(self._dependency_service.store, add_edge=edge)
            post_store = EdgeOverrideDependencyStore(self._dependency_service.store, remove_edge=edge_key)

        pre_dependency = LLMAgentTaskDependencyService(self._lifecycle_service, store=pre_store)
        post_dependency = LLMAgentTaskDependencyService(self._lifecycle_service, store=post_store)

        if change_type == DEPENDENCY_ADDED:
            reachable = set(post_dependency.get_dependencies(task_id, transitive=True)) | {task_id}
            edges = {node: post_dependency.get_dependencies(node) for node in reachable}
            if task_id in cyclic_step_ids(sorted(reachable), edges):
                return self._unresolved(
                    task_id, f"adding a dependency on {dependency_task_id!r} would create a cycle"
                )

        verb = "gains" if change_type == DEPENDENCY_ADDED else "loses"
        description = f"task {task_id!r} {verb} a dependency on {dependency_task_id!r}"
        return self._compare(
            task_id, self._lifecycle_service, pre_dependency, self._lifecycle_service, post_dependency, description
        )

    def _compare(self, task_id, pre_lifecycle, pre_dependency, post_lifecycle, post_dependency, description):
        impact = self._dependency_impact_service.analyze(task_id)
        candidates = sorted({task_id} | set(impact.transitive_dependents))

        pre_plans = {node: self._build_plan(pre_lifecycle, pre_dependency, node) for node in candidates}
        post_plans = {node: self._build_plan(post_lifecycle, post_dependency, node) for node in candidates}

        affected, newly_blocked, newly_ready, unchanged = [], [], [], []
        for node in candidates:
            pre_plan, post_plan = pre_plans[node], post_plans[node]
            if pre_plan == post_plan:
                unchanged.append(node)
                continue
            affected.append(node)
            if pre_plan.ready and not post_plan.ready:
                newly_blocked.append(node)
            elif not pre_plan.ready and post_plan.ready:
                newly_ready.append(node)

        impact_summary = (
            f"{description}: {len(affected)} affected ({len(newly_ready)} newly ready, "
            f"{len(newly_blocked)} newly blocked), {len(unchanged)} unchanged, "
            f"{len(candidates)} cache entr{'y' if len(candidates) == 1 else 'ies'} invalidated"
        )

        return AgentTaskDependencyChangeImpact(
            task_id=task_id,
            affected_tasks=affected,
            invalidated_cache_entries=candidates,
            newly_blocked_tasks=newly_blocked,
            newly_ready_tasks=newly_ready,
            unchanged_tasks=unchanged,
            impact_summary=impact_summary,
        )

    @staticmethod
    def _build_plan(lifecycle_service, dependency_service, node_id: str):
        resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
        return LLMAgentTaskDependencyReadinessService(resolver).build_plan(node_id)

    @staticmethod
    def _unresolved(task_id, reason: str) -> AgentTaskDependencyChangeImpact:
        return AgentTaskDependencyChangeImpact(
            task_id=task_id,
            impact_summary=f"unresolved: {reason}",
            unresolved_reason=reason,
        )
