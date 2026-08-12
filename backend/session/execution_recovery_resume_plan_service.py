from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_recovery_resume_plan_error import (
    ExecutionRecoveryResumePlanError,
)

from .execution_recovery_resume_plan import (
    ExecutionRecoveryResumePlan,
)


class ExecutionRecoveryResumePlanService:
    """
    Declares, for an interrupted execution session, an explicit plan
    of where it should resume.

    Checkpoints and their validation outcome are assumed to already
    exist elsewhere; this service depends on plain resolver
    callables for them rather than a concrete store:
    - checkpoint_resolver(checkpoint_id) -> checkpoint or None
    - checkpoint_validation_resolver(checkpoint_id) -> True if the
      checkpoint has passed validation, False or None otherwise

    Behavior:
    - create() declares a new plan for a session, resuming from a
      valid checkpoint; a session may only have one active plan at a
      time
    - resolve() looks up a session's active plan, or None if it has
      none
    - update() repoints an active plan at a different valid
      checkpoint; the plan's stage_id always tracks the checkpoint
      it currently references
    - cancel() permanently retires a plan; a cancelled plan can
      never resume, be updated, or be cancelled again, and its
      session becomes free to receive a new plan

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, checkpoint_resolver, checkpoint_validation_resolver):
        self._checkpoint_resolver = checkpoint_resolver
        self._checkpoint_validation_resolver = checkpoint_validation_resolver
        self._plans_by_id = {}
        self._active_plan_id_by_session = {}
        self._cancelled_plan_ids = set()
        self._lock = RLock()

    def create(self, session_id: str, checkpoint_id: str) -> ExecutionRecoveryResumePlan:
        """
        Declare a new resume plan for a session, resuming from a
        valid checkpoint.

        Raises:
            ExecutionRecoveryResumePlanError: If session_id or
                checkpoint_id is None or blank, no checkpoint is
                known under checkpoint_id, it has not passed
                validation, or the session already has an active
                plan
        """

        self._validate_id(session_id, "session ID")

        checkpoint = self._resolve_valid_checkpoint(checkpoint_id)

        with self._lock:
            if session_id in self._active_plan_id_by_session:
                raise ExecutionRecoveryResumePlanError(
                    f"Session ID {session_id!r} already has an active resume plan."
                )

            plan = ExecutionRecoveryResumePlan(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                stage_id=checkpoint.stage_id,
            )

            self._plans_by_id[plan.plan_id] = plan
            self._active_plan_id_by_session[session_id] = plan.plan_id

            return plan

    def resolve(self, session_id: str) -> ExecutionRecoveryResumePlan | None:
        """
        Look up a session's active resume plan.

        Raises:
            ExecutionRecoveryResumePlanError: If session_id is None
                or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            plan_id = self._active_plan_id_by_session.get(session_id)

            return self._plans_by_id.get(plan_id) if plan_id is not None else None

    def update(self, plan_id: str, checkpoint_id: str) -> ExecutionRecoveryResumePlan:
        """
        Repoint an active plan at a different valid checkpoint,
        updating its stage_id to match.

        Raises:
            ExecutionRecoveryResumePlanError: If plan_id or
                checkpoint_id is None or blank, no plan is known
                under plan_id, it has been cancelled, no checkpoint
                is known under checkpoint_id, or it has not passed
                validation
        """

        self._validate_id(plan_id, "plan ID")

        checkpoint = self._resolve_valid_checkpoint(checkpoint_id)

        with self._lock:
            plan = self._resolve_plan(plan_id)

            updated = replace(plan, checkpoint_id=checkpoint_id, stage_id=checkpoint.stage_id)

            self._plans_by_id[plan_id] = updated

            return updated

    def cancel(self, plan_id: str) -> None:
        """
        Permanently retire a plan. A cancelled plan can never
        resume, be updated, or be cancelled again, and its session
        becomes free to receive a new plan.

        Raises:
            ExecutionRecoveryResumePlanError: If plan_id is None or
                blank, no plan is known under it, or it has already
                been cancelled
        """

        self._validate_id(plan_id, "plan ID")

        with self._lock:
            plan = self._resolve_plan(plan_id)

            del self._plans_by_id[plan_id]

            if self._active_plan_id_by_session.get(plan.session_id) == plan_id:
                del self._active_plan_id_by_session[plan.session_id]

            self._cancelled_plan_ids.add(plan_id)

    def _resolve_valid_checkpoint(self, checkpoint_id: str):
        self._validate_id(checkpoint_id, "checkpoint ID")

        checkpoint = self._checkpoint_resolver(checkpoint_id)

        if checkpoint is None:
            raise ExecutionRecoveryResumePlanError(f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.")

        if not self._checkpoint_validation_resolver(checkpoint_id):
            raise ExecutionRecoveryResumePlanError(
                f"Cannot use checkpoint ID {checkpoint_id!r} in a resume plan: it has not passed validation."
            )

        return checkpoint

    def _resolve_plan(self, plan_id: str) -> ExecutionRecoveryResumePlan:
        if plan_id in self._cancelled_plan_ids:
            raise ExecutionRecoveryResumePlanError(f"Resume plan ID {plan_id!r} has been cancelled.")

        plan = self._plans_by_id.get(plan_id)

        if plan is None:
            raise ExecutionRecoveryResumePlanError(f"No resume plan is known under plan ID {plan_id!r}.")

        return plan

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryResumePlanError(f"Cannot use an empty or blank {field_name}.")
