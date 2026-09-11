from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


class InvalidDeadLetterEntryError(ValueError):
    """Raised when a DeadLetterEntry's own fields are invalid, or
    dead_letter()/get()/list()/restore() is given invalid arguments."""


@dataclass(frozen=True)
class DeadLetterEntry(object):
    """Durable record that task_id has been permanently pulled out of
    normal queue handling -- not a second lifecycle or retry record
    (Rule: "do not invent a second task lifecycle or retry system"):
    this entry only ever says *that* task_id was set aside and *why*,
    never anything about what should happen to it next (there is no
    retry count, no schedule, no outcome field here at all).

    reason is the caller-supplied, immediate reason dead_letter() was
    called (e.g. "exceeded max retries", "manually excluded by
    operator") -- metadata is deliberately kept separate from it: a
    snapshot of *existing* failure information already recorded
    elsewhere (Rule: "Retain the original failure reason/context using
    existing references"), specifically task_id's own Commit #1
    AgentTask.current_state/previous_state/transition_reason at
    dead_letter() time, plus (only when a
    backend.agent_task_state_history.LLMAgentTaskStateHistoryService
    was supplied) its own most recent TaskTransitionRecord, verbatim --
    never a re-derived or summarized explanation of its own, the same
    "carry the step's own recorded error verbatim" discipline backend.
    agent_failure_handling.LLMAgentFailureClassification.reason already
    establishes for a comparable, narrower (single plan-step) case.

    Attributes:
        task_id: The backend.agent_task_lifecycle.AgentTask.task_id set
            aside. Exactly one live DeadLetterEntry exists per task_id
            at a time.
        reason: Why dead_letter() was called, verbatim.
        metadata: A dict snapshot of existing failure/lifecycle
            information already recorded for task_id -- never this
            service's own opinion about why task_id failed.
        failed_at: When this entry was created.
    """

    task_id: str
    reason: str
    metadata: dict = field(default_factory=dict)
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidDeadLetterEntryError("task_id is required and must be a non-empty string")
        if not self.reason or not isinstance(self.reason, str):
            raise InvalidDeadLetterEntryError("reason is required and must be a non-empty string")
        if not isinstance(self.metadata, dict):
            raise InvalidDeadLetterEntryError("metadata must be a dict")
        if not isinstance(self.failed_at, datetime):
            raise InvalidDeadLetterEntryError("failed_at must be a datetime")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["failed_at"] = self.failed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DeadLetterEntry":
        payload = dict(data)
        value = payload.get("failed_at")
        if isinstance(value, str):
            payload["failed_at"] = datetime.fromisoformat(value)
        return cls(**payload)
