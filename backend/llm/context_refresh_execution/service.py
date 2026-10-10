import dataclasses
from datetime import datetime, timezone

from ..context_refresh import LLMContextRefreshService
from ..context_version import UnknownContextVersionError
from ..project_context import InvalidContentError, SecretContentError, UnknownProjectContextError
from .models import FAILED, PARTIAL, ROLLED_BACK, SUCCEEDED, LLMContextRefreshExecution

_MISSING = object()


class UnknownExecutionError(KeyError):
    """Raised when status()/rollback() names an execution_id that was never created."""


class NoApprovedActionsError(ValueError):
    """Raised when execute() is given a plan with no approved refresh_actions."""


class InvalidRollbackError(ValueError):
    """Raised when rollback() is asked to undo an execution that never applied,
    or that has already been rolled back."""


class LLMContextRefreshExecutionService:
    """Applies a Commit #10 refresh plan through the repository's real interfaces.

    Reuses, never re-implements: Commit #10's own validate() (a plan must
    still be valid right now, or execute() never starts), Commit #1's
    LLMProjectContextService.update() (the only way content ever changes,
    with its own content/secret validation applied as normal), Commit #2's
    LLMContextVersionService.snapshot() (every state this service touches,
    before and after, becomes a new version -- history is only ever added
    to, never rewritten), and Commit #6's LLMContextProvenanceService.attach()
    (a refreshed context gets new provenance recording exactly what it was
    refreshed from; its prior provenance records remain in the trail).

    Each refresh_action is applied independently: one invalid or now-secret
    source fails that action alone and leaves the context exactly as it
    was, it does not undo an action that already succeeded and does not
    stop the remaining actions from being tried.
    """

    def __init__(self, refresh_service: LLMContextRefreshService):
        self.refresh_service = refresh_service
        self.context_service = refresh_service.context_service
        self.provenance_service = refresh_service.provenance_service
        self.version_service = refresh_service.provenance_service.version_service
        self._executions: dict[str, LLMContextRefreshExecution] = {}
        self._previous_versions: dict[str, int] = {}

    def execute(self, plan_id: str) -> LLMContextRefreshExecution:
        # Rule: a plan must be validated before execution. Any
        # UnknownRefreshPlanError/InvalidRefreshPlanError Commit #10 raises
        # here propagates unchanged -- no execution record is created for a
        # plan that never passed validation.
        self.refresh_service.validate(plan_id)
        plan = self.refresh_service.get(plan_id)

        if not plan.refresh_actions:
            raise NoApprovedActionsError(
                f"plan {plan_id!r} has no approved refresh actions to execute"
            )

        if self.version_service is None:
            raise ValueError("no version service is wired; cannot create refresh versions")

        created_at = datetime.now(timezone.utc)

        # Captured once, before anything is touched, so rollback always has
        # a concrete prior state to restore -- whether or not this context
        # had ever been explicitly versioned before.
        previous_version = self.version_service.snapshot(plan.context_id)

        successes = 0
        failures = 0
        for action in plan.refresh_actions:
            if self._apply_action(plan.context_id, action):
                successes += 1
            else:
                failures += 1

        if successes and not failures:
            status = SUCCEEDED
        elif successes:
            status = PARTIAL
        else:
            status = FAILED

        execution = LLMContextRefreshExecution(
            plan_id=plan_id,
            status=status,
            refreshed_context_ids=(plan.context_id,) if successes else (),
            created_at=created_at,
            completed_at=datetime.now(timezone.utc),
        )

        self._executions[execution.execution_id] = execution
        self._previous_versions[execution.execution_id] = previous_version.version
        return execution

    def status(self, execution_id: str) -> LLMContextRefreshExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

    def rollback(self, execution_id: str) -> LLMContextRefreshExecution:
        try:
            execution = self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

        if execution.status not in (SUCCEEDED, PARTIAL):
            raise InvalidRollbackError(
                f"execution {execution_id!r} is {execution.status!r}; nothing to roll back"
            )

        previous_version_number = self._previous_versions[execution_id]

        for context_id in execution.refreshed_context_ids:
            previous_version = self.version_service.get(context_id, previous_version_number)
            self.context_service.update(context_id, previous_version.content)
            # the restored state becomes a new version too -- rollback is
            # forward history, not a rewrite of what happened
            self.version_service.snapshot(context_id)

        rolled_back = dataclasses.replace(execution, status=ROLLED_BACK)
        self._executions[execution_id] = rolled_back
        return rolled_back

    # -- internals ------------------------------------------------------

    def _apply_action(self, context_id: str, action: dict) -> bool:
        new_content, resolved_version = self._resolve_current_source(action)
        if new_content is _MISSING:
            return False

        try:
            self.context_service.update(context_id, new_content)
        except (InvalidContentError, SecretContentError):
            # existing context is left exactly as it was
            return False

        new_version = self.version_service.snapshot(context_id)

        # A context_version source that IS this same context (refreshing a
        # context from its own version history) makes the snapshot just
        # taken the definitive marker for "this content, this version" --
        # use its number, since it has already superseded the one resolved
        # a moment earlier. Any other source's version (another context's
        # history, a research artifact, or none for a project_context
        # source) is unaffected by this context's own bookkeeping, so the
        # freshly resolved value stands. Without this distinction, a
        # self-referential context_version refresh would immediately
        # re-report as stale: the snapshot above always moves this
        # context's own "latest" one step past whatever was resolved.
        source_version = (
            new_version.version
            if action["source_type"] == "context_version" and action["source_id"] == context_id
            else resolved_version
        )

        self.provenance_service.attach(
            context_id,
            {
                "source_type": action["source_type"],
                "source_id": action["source_id"],
                "source_version": source_version,
                "excerpt": f"refreshed from {action['source_type']} {action['source_id']}",
            },
        )
        return True

    def _resolve_current_source(self, action: dict):
        """(content, version) currently held by action's source, or (_MISSING, None)."""
        source_type = action["source_type"]
        source_id = action["source_id"]

        if source_type == "context_version":
            version_service = self.provenance_service.version_service
            if version_service is None:
                return _MISSING, None
            try:
                latest = version_service.latest(source_id)
            except UnknownContextVersionError:
                return _MISSING, None
            return latest.content, latest.version

        if source_type == "research_artifact":
            artifact_store = self.provenance_service.artifact_store
            if artifact_store is None:
                return _MISSING, None
            artifact = artifact_store.get(source_id)
            if artifact is None:
                return _MISSING, None
            return artifact.content, artifact.version

        if source_type == "project_context":
            try:
                source = self.context_service.get(source_id)
            except UnknownProjectContextError:
                return _MISSING, None
            return source.content, None

        return _MISSING, None
