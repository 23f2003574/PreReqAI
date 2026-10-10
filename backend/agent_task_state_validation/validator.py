from backend.agent_task_lifecycle import (
    CREATED,
    STATES,
    TERMINAL_STATES,
    AgentTask,
    LLMAgentTaskLifecycleService,
)

from .models import AgentTaskStateValidationResult, TransitionValidationResult

# The identity/definition fields Commit #1's own AgentTask requires --
# copied from LLMAgentTaskLifecycleService._validate_identity()'s own
# requiredness rules (agent_id/scope_id/objective), plus task_id itself
# (always populated by Commit #1's own default_factory, so a blank one
# can only mean a malformed record). Not a second copy of Commit #1's
# validation *logic* -- create() itself remains the only place a task is
# ever rejected at creation time; this only re-checks the same
# requiredness on an already-existing record, the "no required lifecycle
# metadata is missing" half of this commit's own Rule.
_REQUIRED_TEXT_FIELDS = ("task_id", "agent_id", "scope_id", "objective")


class LLMAgentTaskStateValidator:
    """Pure, read-only validation of Commit #1 AgentTask lifecycle state
    and of (current_state, target_state) transitions -- never applies a
    transition (Commit #1's own LLMAgentTaskLifecycleService.transition()
    remains the only thing that does that) and never records anything
    (Commit #2's own LLMAgentTaskStateHistoryService remains the only
    thing that does that). Every method here only ever reads its
    arguments; none of them mutate, persist, or transition anything.

    Every transition-legality check delegates to Commit #1's own
    LLMAgentTaskLifecycleService.can_transition() -- Rule: "use one
    authoritative transition definition." This module holds no second
    copy of the state graph, and STATES/TERMINAL_STATES/CREATED are
    Commit #1's own, imported rather than redeclared, so a change to
    Commit #1's own lifecycle graph is picked up here automatically,
    never drifting out of sync with it.

    Unknown/invalid states are always reported as errors, never
    silently treated as any particular known state (Rule: "never
    silently coerce invalid states") -- see validate()/
    validate_transition()'s own docstrings for exactly what "unknown"
    means in each.
    """

    @staticmethod
    def validate(task) -> AgentTaskStateValidationResult:
        """Check one AgentTask for internal consistency: a known
        current_state (and previous_state, when set), required identity/
        definition fields present, and a previous_state/current_state
        pair that is itself a legal transition (or, for a freshly
        CREATED task, no previous_state at all).

        Never raises: a task that is not even an AgentTask, or whose
        fields are the wrong type entirely, is reported as an invalid
        result rather than raising InvalidAgentTaskError -- that error
        belongs to Commit #1's own create()/transition(), which is
        never called here.
        """
        errors = []
        warnings = []

        if not isinstance(task, AgentTask):
            return AgentTaskStateValidationResult(
                valid=False,
                current_state=None,
                errors=[f"expected an AgentTask, got {type(task).__name__}"],
            )

        current_state = task.current_state
        if current_state not in STATES:
            errors.append(f"current_state {current_state!r} is not one of {sorted(STATES)}")

        previous_state = task.previous_state
        if previous_state is not None and previous_state not in STATES:
            errors.append(f"previous_state {previous_state!r} is not one of {sorted(STATES)}")

        if current_state == CREATED and previous_state is not None:
            errors.append("a task in the CREATED state must not have a previous_state")
        elif current_state in STATES and current_state != CREATED and previous_state is None:
            errors.append(f"a task in {current_state!r} must have a previous_state recorded")
        elif (
            current_state in STATES
            and previous_state is not None
            and previous_state in STATES
            and not LLMAgentTaskLifecycleService.can_transition(previous_state, current_state)
        ):
            errors.append(f"previous_state {previous_state!r} cannot legally reach current_state {current_state!r}")

        for field_name in _REQUIRED_TEXT_FIELDS:
            value = getattr(task, field_name, None)
            if not value or not isinstance(value, str):
                errors.append(f"{field_name} is required and must be a non-empty string")

        if not isinstance(task.definition, dict):
            errors.append(f"definition must be a dict, got {type(task.definition).__name__}")

        if current_state in TERMINAL_STATES and not task.transition_reason:
            warnings.append(f"task reached terminal state {current_state!r} without a transition_reason")

        return AgentTaskStateValidationResult(
            valid=not errors,
            current_state=current_state,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def validate_transition(current_state: str, target_state: str) -> TransitionValidationResult:
        """Check whether target_state is a legal move from current_state.

        Unknown states (either one not in Commit #1's own STATES) are
        always reported as an error naming exactly which argument is
        unknown, and no further transition-legality check runs against
        it in that case -- Rule: "never silently coerce invalid
        states" means an unknown current_state/target_state is never
        treated as though it were some particular known one.
        """
        errors = []
        warnings = []

        if current_state not in STATES:
            errors.append(f"current_state {current_state!r} is not one of {sorted(STATES)}")
        if target_state not in STATES:
            errors.append(f"target_state {target_state!r} is not one of {sorted(STATES)}")

        if not errors:
            if current_state in TERMINAL_STATES and current_state != target_state:
                errors.append(
                    f"cannot transition out of terminal state {current_state!r} to {target_state!r}"
                )
            elif not LLMAgentTaskLifecycleService.can_transition(current_state, target_state):
                errors.append(f"transition from {current_state!r} to {target_state!r} is not permitted")
            elif current_state == target_state:
                warnings.append(f"{current_state!r} to itself is a no-op, not a real transition")

        return TransitionValidationResult(
            valid=not errors,
            current_state=current_state,
            target_state=target_state,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def is_terminal(state: str) -> bool:
        """Whether state is one Commit #1 never permits leaving (except
        to itself -- see LLMAgentTaskLifecycleService.can_transition()'s
        own docstring). An unknown state is never terminal -- it is not
        any state at all."""
        return state in TERMINAL_STATES
