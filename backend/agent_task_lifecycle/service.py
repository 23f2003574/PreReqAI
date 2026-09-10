from typing import Optional

from .in_memory_store import InMemoryAgentTaskStore, InMemoryAgentTaskTransitionStore
from .models import (
    CREATED,
    STATES,
    TRANSITIONS,
    AgentTask,
    InvalidAgentTaskError,
    InvalidTaskTransitionError,
    TaskTransitionRecord,
    UnknownAgentTaskError,
)
from .store import AgentTaskStore, AgentTaskTransitionStore


class LLMAgentTaskLifecycleService:
    """Owns one AgentTask's lifecycle state -- create/get/transition --
    and nothing else. This service never executes a task, never plans
    one (backend.agent_task_planning already owns that), and never holds
    a task's own working data (backend.agent_task_context already owns
    that, keyed by its own, separately-generated task_id); it only
    answers "what state is this task in, and how did it get there."

    transition() is the sole way current_state ever changes, and every
    change it makes is validated against can_transition() first --
    Rule: "Invalid transitions must fail explicitly," never silently
    clamped or ignored. A transition whose target_state equals the
    task's own current current_state is a deliberate exception: it
    returns the task unchanged, mutates nothing, and appends no new
    history entry -- the same "repeating an already-applied change is a
    no-op, not an error" convention
    backend.agent_policy_engine.LLMAgentPolicyService.archive() already
    establishes for an already-ARCHIVED policy.

    Every other successful transition is recorded, in order, as a new
    models.TaskTransitionRecord via transition_store -- create() itself
    writes the first one (from_state=None, to_state=CREATED) -- so a
    task's complete transition trail (Rule: "Every successful transition
    records history") is always reachable through history(), never only
    inferable from the task's own current_state/previous_state pair.
    """

    def __init__(self, store: AgentTaskStore = None, transition_store: AgentTaskTransitionStore = None):
        self.store = store if store is not None else InMemoryAgentTaskStore()
        self.transition_store = transition_store if transition_store is not None else InMemoryAgentTaskTransitionStore()

    def create(self, task_definition: dict) -> AgentTask:
        """Create a new AgentTask in the CREATED state from
        task_definition.

        task_definition must be a dict carrying at least agent_id,
        scope_id, and objective; every other key is preserved verbatim,
        unvalidated and uninterpreted, as the created task's own
        definition (this service holds no opinion on what a task
        actually needs to run -- see this module's own AgentTask
        docstring). An explicit task_id may be supplied to control the
        created task's own identity; otherwise one is generated.

        Raises:
            InvalidAgentTaskError: If task_definition is not a dict, is
                missing agent_id/scope_id/objective, or gives a task_id
                that is not a non-empty string
        """
        if not isinstance(task_definition, dict):
            raise InvalidAgentTaskError("task_definition must be a dict")

        agent_id = task_definition.get("agent_id")
        scope_id = task_definition.get("scope_id")
        objective = task_definition.get("objective")
        self._validate_identity(agent_id, scope_id, objective)

        task_id = task_definition.get("task_id")
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise InvalidAgentTaskError("task_id must be a non-empty string when given")

        kwargs = dict(agent_id=agent_id, scope_id=scope_id, objective=objective, definition=dict(task_definition))
        if task_id is not None:
            kwargs["task_id"] = task_id

        task = self.store.save(AgentTask(**kwargs))
        self._record_transition(task.task_id, from_state=None, to_state=CREATED, reason=None)
        return task

    def get(self, task_id: str) -> AgentTask:
        """The current lifecycle record for task_id.

        Raises:
            UnknownAgentTaskError: If task_id was never created
        """
        task = self.store.get(task_id)
        if task is None:
            raise UnknownAgentTaskError(task_id)
        return task

    @staticmethod
    def can_transition(current_state: str, target_state: str) -> bool:
        """Whether target_state is reachable from current_state.

        A pure function of the two states alone -- no task lookup, no
        side effect -- so a caller can check reachability before ever
        attempting transition(). Unknown states (not one of
        models.STATES) are never reachable, in either direction. Staying
        in current_state is always reported reachable, even from a
        terminal one (models.TERMINAL_STATES), matching transition()'s
        own idempotent-no-op handling of a repeated same-state call --
        never mistaken for "terminal states permit further progress."
        """
        if current_state not in STATES or target_state not in STATES:
            return False
        if current_state == target_state:
            return True
        return target_state in TRANSITIONS.get(current_state, frozenset())

    def transition(self, task_id: str, target_state: str, reason: str = None) -> AgentTask:
        """Move task_id to target_state, recording reason (if given) and
        appending a new history entry -- unless target_state already
        equals the task's own current current_state, in which case this
        is a no-op: the task is returned unchanged, and no new history
        entry is appended (see this class's own docstring).

        Raises:
            UnknownAgentTaskError: If task_id was never created
            InvalidAgentTaskError: If reason is given but is not a
                string
            InvalidTaskTransitionError: If target_state is not one of
                models.STATES, or is not reachable from task_id's own
                current_state per can_transition() (this includes every
                attempt to leave a terminal state for anything other
                than itself)
        """
        if reason is not None and not isinstance(reason, str):
            raise InvalidAgentTaskError("reason must be a string when given")

        task = self.get(task_id)

        if not self.can_transition(task.current_state, target_state):
            raise InvalidTaskTransitionError(
                f"cannot transition task {task_id!r} from {task.current_state!r} to {target_state!r}"
            )

        if task.current_state == target_state:
            return task

        previous_state = task.current_state
        task.previous_state = previous_state
        task.current_state = target_state
        task.transition_reason = reason

        saved = self.store.save(task)
        self._record_transition(task_id, from_state=previous_state, to_state=target_state, reason=reason)
        return saved

    def history(self, task_id: str) -> list:
        """task_id's complete, in-order transition trail, as
        models.TaskTransitionRecord entries -- the first always
        (from_state=None, to_state=CREATED).

        Raises:
            UnknownAgentTaskError: If task_id was never created
        """
        self.get(task_id)
        return self.transition_store.list_for_task(task_id)

    def _record_transition(self, task_id: str, from_state: Optional[str], to_state: str, reason: Optional[str]) -> TaskTransitionRecord:
        return self.transition_store.save(
            TaskTransitionRecord(task_id=task_id, from_state=from_state, to_state=to_state, reason=reason)
        )

    @staticmethod
    def _validate_identity(agent_id, scope_id, objective) -> None:
        if not agent_id or not isinstance(agent_id, str):
            raise InvalidAgentTaskError("task_definition.agent_id is required and must be a non-empty string")
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidAgentTaskError(
                "task_definition.scope_id is required and must identify a project/notebook/API"
            )
        if not objective or not isinstance(objective, str):
            raise InvalidAgentTaskError("task_definition.objective is required and must be a non-empty string")
