from dataclasses import dataclass

# Action vocabulary for this module's own ExecutionControlResult -- the
# same CANCELLED/TIMED_OUT words backend.llm.tool_execution already uses
# for its own execution statuses, reused here for the same real-world
# concept but in a different role: Commit #7's own
# LLMAgentCapabilityExecution has no CANCELLED/TIMED_OUT status of its
# own (only RUNNING/SUCCEEDED/FAILED -- see Rule "reuse existing task/
# execution state transitions" / "no invented runtime infrastructure":
# no new status is added to that model), so a cancelled or timed-out
# execution's own new_status is always Commit #7's existing FAILED.
# action is what actually distinguishes a cancellation from a timeout
# from a no-op check, entirely at this module's own level.
ACTION_CANCELLED = "CANCELLED"
ACTION_TIMED_OUT = "TIMED_OUT"
ACTION_NONE = "NONE"
ACTIONS = frozenset({ACTION_CANCELLED, ACTION_TIMED_OUT, ACTION_NONE})


@dataclass(frozen=True)
class ExecutionControlResult:
    """cancel()/check_timeout()'s outcome for one execution_id.

    previous_status/new_status are Commit #7's own RUNNING/SUCCEEDED/
    FAILED vocabulary, reused as-is; they are equal whenever action is
    ACTION_NONE (nothing changed) and previous_status is RUNNING while
    new_status is FAILED exactly when action is ACTION_CANCELLED or
    ACTION_TIMED_OUT (the one real transition either method ever makes,
    always through Commit #7's own fail()). reason is always populated.
    """

    execution_id: str
    action: str
    previous_status: str
    new_status: str
    reason: str
