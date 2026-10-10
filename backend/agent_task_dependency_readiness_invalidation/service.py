from backend.agent_task_dependency_readiness_cache import LLMAgentTaskDependencyReadinessCache


class LLMAgentTaskDependencyReadinessInvalidationService:
    """The single place that decides which Commit #9 cache entries a
    real task/dependency change affects, and evicts exactly those --
    never a second event bus, never a second cache (Rule: "do not
    introduce a second event bus or cache system").

    Commit #9 already had this same invalidation *behavior*, but
    embedded directly inside its own tracked-wrapper subclasses
    (LLMAgentTaskLifecycleCacheInvalidatingService/
    LLMAgentTaskDependencyCacheInvalidatingService each called
    self._cache.invalidate()/invalidate_dependents() inline). This
    commit extracts that decision-making into its own dedicated,
    independently testable service -- the exact same "the entity
    service/wrapper never owns X's policy directly; a separate service
    does, the wrapper just calls into it" split Commit #2's own
    backend.agent_task_state_history already established for history
    recording (there, over Commit #1's transitions). Commit #9's own
    wrappers (now living in this module's own .tracked) call this
    service's on_task_state_changed()/on_dependency_changed() instead
    of touching the cache directly -- Rule: "reuse Commit #9 cache
    APIs," now from exactly one call site instead of two duplicated
    ones.

    This project has no separate event bus or change-notification
    framework to reuse outside its own established "a thin subclass
    wrapper calls a hook after a real mutation succeeds" convention
    (Commit #2's own tracked.py, Commit #9's own tracked.py, and this
    module's own .tracked below) -- Rule: "reuse the repository's
    existing change/event mechanism" is satisfied by continuing that
    exact convention, not by inventing publish/subscribe machinery this
    repository does not otherwise have.

    Every method here only ever calls Commit #9's own
    LLMAgentTaskDependencyReadinessCache.invalidate()/
    invalidate_dependents() -- both already safe to call for an entry
    that is not cached (a no-op, never an error) and safe to call
    repeatedly (Rules: "invalidation must be safe if an entry does not
    exist" / "repeated invalidation is safe/idempotent"). Neither method
    here ever recomputes a plan, transitions a task, or changes a
    dependency edge itself (Rule: "invalidation only; never recompute or
    execute tasks") -- this service has no reference to Commit #1's own
    LLMAgentTaskLifecycleService or Commit #5's own
    LLMAgentTaskDependencyService at all, only to the cache.

    Commit #1 has no task deletion (its own store docstring: "a task is
    retired by transitioning it into a terminal state," never removed),
    so there is no on_task_deleted() here -- Goal's own "handle ...
    task deletion if those operations exist" is satisfied by there
    being nothing to handle.
    """

    def __init__(self, cache: LLMAgentTaskDependencyReadinessCache):
        self._cache = cache

    def on_task_state_changed(self, task_id: str, old_state: str, new_state: str) -> None:
        """A Commit #1 transition just moved task_id from old_state to
        new_state (successfully -- callers only ever report a change
        that actually happened).

        old_state == new_state is Commit #1's own idempotent no-op
        (repeating a transition to the current state) -- nothing
        actually changed, so nothing is invalidated (Rule: "never
        invalidate unrelated task graphs" -- a no-op touches no graph
        at all). Otherwise: task_id's own cached plan is invalidated
        (its own current_state is exactly what that plan was computed
        from), and every task currently downstream of task_id is
        invalidated too, since any of their own cached plans could have
        read task_id's old state as part of their resolution.
        """
        if old_state == new_state:
            return
        self._cache.invalidate(task_id)
        self._cache.invalidate_dependents(task_id)

    def on_dependency_changed(self, task_id: str, dependency_task_id: str) -> None:
        """A Commit #5 dependency edge task_id -> dependency_task_id was
        just added or removed (successfully). The same handling either
        way: task_id's own dependency graph changed shape, so its own
        cached plan is invalidated, and so is every task currently
        downstream of task_id (their own resolutions could now differ
        too). dependency_task_id's own cached entry is never touched --
        gaining or losing a dependent never changes what
        dependency_task_id itself still needs before it is ready.
        """
        self._cache.invalidate(task_id)
        self._cache.invalidate_dependents(task_id)
