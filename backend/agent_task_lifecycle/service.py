from .in_memory_store import InMemoryAgentTaskStore
from .models import (
    STATES,
    TRANSITIONS,
    AgentTask,
    InvalidAgentTaskError,
    InvalidTaskTransitionError,
    UnknownAgentTaskError,
)
from .store import AgentTaskStore


class LLMAgentTaskLifecycleService:
    """Owns one AgentTask's lifecycle state -- create/get/transition --
    and nothing else. This service never executes a task, never plans
    one (backend.agent_task_planning already owns that), never holds a
    task's own working data (backend.agent_task_context already owns
    that, keyed by its own, separately-generated task_id), and never
    records its own transition history (backend.agent_task_state_history
    owns that entirely, from the outside -- see this class's own
    docstring below); it only answers "what state is this task in right
    now, and is a given move legal."

    transition() is the sole way current_state ever changes, and every
    change it makes is validated against can_transition() first --
    Rule: "Invalid transitions must fail explicitly," never silently
    clamped or ignored. A transition whose target_state equals the
    task's own current current_state is a deliberate exception: it
    returns the task unchanged and mutates nothing -- the same
    "repeating an already-applied change is a no-op, not an error"
    convention backend.agent_policy_engine.LLMAgentPolicyService.
    archive() already establishes for an already-ARCHIVED policy.

    Recording a durable, queryable trail of every transition is
    deliberately not this class's job: backend.agent_task_state_history.
    LLMAgentTaskStateHistoryService owns that, called from
    backend.agent_task_state_history.tracked.
    LLMAgentTaskLifecycleHistoryTrackedService -- a thin subclass that
    delegates every method here completely unchanged and only
    afterward records what happened. Nothing in this class imports or
    references that module at all, so "lifecycle transitions remain
    owned by LLMAgentTaskLifecycleService" holds structurally: this
    class cannot regress into recording history again by accident.
    """

    def __init__(self, store: AgentTaskStore = None):
        self.store = store if store is not None else InMemoryAgentTaskStore()

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

        return self.store.save(AgentTask(**kwargs))

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
        """Move task_id to target_state, recording reason (if given) --
        unless target_state already equals the task's own current
        current_state, in which case this is a no-op: the task is
        returned unchanged (see this class's own docstring).

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

        task.previous_state = task.current_state
        task.current_state = target_state
        task.transition_reason = reason

        return self.store.save(task)

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
