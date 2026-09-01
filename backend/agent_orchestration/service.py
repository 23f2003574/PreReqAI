from backend.agent_execution_budget import UnknownExecutionBudgetError
from backend.agent_execution_context import DuplicateStepContextError
from backend.agent_execution_scheduling import LLMAgentSchedulerService
from backend.llm.budget import BudgetExceededError


class LLMAgentOrchestrationService:
    """Unifies Commits #1-#12 into one bounded agent workflow.

    Not another agent or workflow framework: every phase the goal names is
    an existing commit's own method, called unchanged --

        planning              Commit #1 planning_service.create()
        validation            Commit #2 validation_service.validate()
        dependency resolution Commit #8 dependency_service (via the
                               Commit #11 scheduler this composes)
        scheduling             Commit #11 LLMAgentSchedulerService, built
                               here from the same dependency/budget/plan-
                               execution services, for introspection
                               (ready_steps()) -- the ordering it would
                               compute is exactly what Commit #4's own
                               execute() already uses internally, so
                               nothing calls it twice
        execution              Commit #4 plan_execution_service.execute(),
                               which runs every step through Commit #3 --
                               unchanged, and still the only step-running
                               loop that exists
        context updates        Commit #7 context_service.record_step()
        failure handling        Commit #4's own stop-on-first-non-success
                               rule; Commit #9's classification is
                               surfaced through report(), not used to
                               auto-retry or auto-replan
        checkpointing/recovery Commit #5 checkpoint_service.save(), Commit
                               #6 recovery_service.recover()
        budget enforcement      Commit #10 budget_service.check()/
                               consume_step()
        reporting               Commit #12 report_service.generate()

    execute() composes budget, context, and checkpointing into Commit #4's
    existing loop through the three hooks that method now accepts
    (on_created/before_step/after_step) -- added there for exactly this
    purpose, rather than this service re-implementing a second loop over
    Commit #3 to get the same effect. Every hook is optional and only
    active for whichever collaborators were actually wired in; omitting
    all of budget/context/checkpoint services reduces execute() to exactly
    Commit #4's own behaviour.

    resume() is Commit #6's recover() itself; the only addition is
    replaying its newly-completed steps into Commit #7's context and
    saving a fresh Commit #5 checkpoint afterward, since recover() does
    neither on its own. cancel() and report() are direct passthroughs to
    Commit #4 and Commit #12.

    Nothing here ever names, imports, or invokes a shell, `eval`, or any
    other means of running arbitrary code: a step is still only ever a
    reference to an already-registered, already-authorized tool, exactly
    as every commit beneath this one already guarantees.
    """

    def __init__(
        self,
        planning_service,
        validation_service,
        step_execution_service,
        plan_execution_service,
        checkpoint_service,
        recovery_service,
        report_service,
        dependency_service=None,
        context_service=None,
        budget_service=None,
    ):
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._step_execution_service = step_execution_service
        self._plan_execution_service = plan_execution_service
        self._checkpoint_service = checkpoint_service
        self._recovery_service = recovery_service
        self._report_service = report_service
        self._dependency_service = dependency_service
        self._context_service = context_service
        self._budget_service = budget_service
        self._scheduler_service = (
            LLMAgentSchedulerService(dependency_service, budget_service, plan_execution_service)
            if dependency_service is not None
            else None
        )

    # -- planning & validation ---------------------------------------------

    def create_plan(self, task: str, context: dict = None):
        """Commit #1's create(), unchanged."""
        return self._planning_service.create(task, context)

    def validate(self, plan_id: str) -> list:
        """Commit #2's validate(), unchanged -- every current finding."""
        return self._validation_service.validate(plan_id)

    def ready_steps(self, execution_id: str) -> list:
        """Commit #11's schedule(): dependency-ready, in-budget, still-running
        steps, in deterministic order. Requires a dependency_service to
        have been wired."""
        if self._scheduler_service is None:
            raise ValueError("no dependency_service was wired; cannot resolve readiness")
        return self._scheduler_service.schedule(execution_id)

    # -- execution -----------------------------------------------------

    def _budget_before_step(self, execution_id, _step_id) -> bool:
        if self._budget_service is None:
            return True
        try:
            self._budget_service.check(execution_id)
        except UnknownExecutionBudgetError:
            return True
        except BudgetExceededError:
            return False
        return True

    def _record_context(self, execution_id, step_execution):
        if self._context_service is None:
            return
        try:
            self._context_service.record_step(execution_id, step_execution.step_id, step_execution)
        except DuplicateStepContextError:
            pass  # already recorded with this same result -- nothing to do

    def execute(self, plan_id: str, subject, timeout: float = None, budget: dict = None):
        """Run plan_id to completion or a stop, enforcing budget and feeding
        context and checkpoints along the way.

        `budget`, when given, is passed straight to Commit #10's
        configure() for this run's freshly-created execution_id -- {
        "max_steps", "max_tokens", "max_cost", "max_duration"}, all
        optional. Ignored if no budget_service was wired.

        Returns Commit #4's own LLMAgentPlanExecution -- one deterministic
        final state (REJECTED/SUCCEEDED/FAILED/CANCELLED), exactly as that
        service already produces it. Validation, dependency ordering,
        authorization, retries, timeouts, and cancellation are all still
        entirely Commit #2/#3/#4's own, unchanged by anything here.
        """

        def on_created(execution_id, _plan_id):
            if self._budget_service is not None:
                self._budget_service.configure(execution_id, **(budget or {}))

        def before_step(execution_id, step_id):
            return self._budget_before_step(execution_id, step_id)

        def after_step(execution_id, step_execution):
            if self._budget_service is not None:
                self._budget_service.consume_step(execution_id, step_execution)
            self._record_context(execution_id, step_execution)
            if self._checkpoint_service is not None:
                self._checkpoint_service.save(execution_id)

        return self._plan_execution_service.execute(
            plan_id, subject, timeout=timeout,
            on_created=on_created, before_step=before_step, after_step=after_step,
        )

    # -- recovery --------------------------------------------------------

    def resume(self, execution_id: str, subject=None, timeout: float = None):
        """Commit #6's recover(), plus replaying newly-completed steps into
        context and saving a fresh checkpoint -- recover() itself does
        neither, by design; composing them here is this method's only job.

        Never reruns a step recover() already skipped as completed: this
        only ever reads Commit #3's own records afterward to catch up
        context, exactly the records recover() itself produced or left
        untouched.
        """
        result = self._recovery_service.recover(execution_id, subject=subject, timeout=timeout)

        if self._context_service is not None:
            plan_id = self._plan_execution_service.get(execution_id).plan_id
            for record in self._step_execution_service.executions(plan_id):
                self._record_context(execution_id, record)

        if self._checkpoint_service is not None:
            self._checkpoint_service.save(execution_id)

        return result

    def cancel(self, execution_id: str):
        """Commit #4's cancel(), unchanged."""
        return self._plan_execution_service.cancel(execution_id)

    # -- reporting ---------------------------------------------------------

    def report(self, execution_id: str) -> dict:
        """Commit #12's generate(), unchanged -- the one deterministic,
        read-only view of everything that happened."""
        return self._report_service.generate(execution_id)
