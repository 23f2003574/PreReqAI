import dataclasses
import re
from datetime import datetime

from backend.agent_checkpointing import UnknownCheckpointError
from backend.agent_execution_budget import UnknownExecutionBudgetError
from backend.agent_failure_handling import NONE as NO_FAILURE
from backend.llm.tool_execution import SUCCEEDED

NOT_ATTEMPTED = "NOT_ATTEMPTED"

# Same secret-redaction convention already used by backend.llm.tool_execution,
# backend.llm.tool_results, backend.llm.tool_audit, and backend.llm.
# context_snapshot. Kept local, as those modules keep their own copies,
# rather than refactoring them here. Applied only to a step's own
# arguments -- the one field on this report's path that reaches here
# without ever having passed through any of those services' own
# redaction: Commit #1's plan carries them exactly as the model proposed
# them, and Commit #3 hands them to a tool handler unredacted by design
# (a handler needs its real arguments to run). Everything else this
# report includes -- a SUCCEEDED step's own result.output, and any
# step's own error -- was already redacted at its source.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)
_REDACTED = "[REDACTED]"


def _redact_text(value) -> str:
    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return _REDACTED
    return text


def _redact_value(value):
    """Redact recursively, the same shape LLMToolResultService._json_safe walks."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {str(_redact_text(str(key))): _redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def _isoformat(value):
    return value.isoformat() if isinstance(value, datetime) else value


class LLMAgentExecutionReportService:
    """Assembles a read-only, structured report from Commits #1-#10's own records.

    Not another execution-tracking system: nothing here is stored, and no
    field is computed from anything other than an existing record --
    Commit #1's plan (for declared order, actions, tools, and arguments),
    Commit #3's own step executions (status, timing, error, and a
    SUCCEEDED step's already-normalized-and-redacted result), Commit #9's
    classify() (which step is failed versus blocked, and why), Commit #8's
    blocked_steps() (which of those are blocked by a dependency rather
    than their own failure), Commit #5's latest checkpoint, and Commit
    #10's budget usage, when each of those optional collaborators is
    wired. generate() composes steps()/failures()/budget()/timeline()
    rather than re-deriving any of their data a second way.

    steps() preserves the plan's own declared order (every method that
    isn't explicitly about time does); timeline() is the one place order
    means "when it actually happened" -- events are sorted by timestamp,
    which need not match declaration order once recovery or scheduling
    has run steps out of sequence.

    A step's arguments are the one field on this path that has never
    passed through any existing redaction -- Commit #1 carries them
    exactly as proposed, and Commit #3 hands them to a tool handler
    unredacted by design -- so this service redacts them itself, with the
    same local convention every other module here already keeps. A
    step's own error and a SUCCEEDED step's result.output are included
    as-is: both were already redacted at their source, and redacting
    again would only be for defense in depth, which this service still
    does for the error text to be safe on its own.
    """

    def __init__(
        self,
        planning_service,
        step_execution_service,
        failure_service,
        dependency_service,
        checkpoint_service=None,
        budget_service=None,
        plan_execution_service=None,
    ):
        self._planning_service = planning_service
        self._step_execution_service = step_execution_service
        self._failure_service = failure_service
        self._dependency_service = dependency_service
        self._checkpoint_service = checkpoint_service
        self._budget_service = budget_service
        self._plan_execution_service = plan_execution_service

    def _plan(self, execution_id: str):
        if self._plan_execution_service is not None:
            try:
                plan_id = self._plan_execution_service.get(execution_id).plan_id
            except Exception:
                plan_id = execution_id
        else:
            plan_id = execution_id
        return self._planning_service.get(plan_id), plan_id

    def _latest_executions(self, plan_id: str) -> dict:
        latest = {}
        for record in self._step_execution_service.executions(plan_id):
            latest[record.step_id] = record
        return latest

    @staticmethod
    def _step_entry(step, record, classification) -> dict:
        return {
            "step_id": step.step_id,
            "action": step.action,
            "tool_name": step.tool_name,
            "depends_on": list(step.depends_on),
            "arguments": _redact_value(step.arguments),
            "status": record.status if record is not None else NOT_ATTEMPTED,
            "category": classification.category,
            "execution_id": record.execution_id if record is not None else None,
            "error": _redact_text(record.error) if record is not None and record.error else None,
            "output": (
                record.result.output
                if record is not None and record.status == SUCCEEDED and record.result is not None
                else None
            ),
            "started_at": _isoformat(record.started_at) if record is not None else None,
            "completed_at": _isoformat(record.completed_at) if record is not None else None,
        }

    def steps(self, execution_id: str) -> list:
        """Every step of the plan, in the plan's own declared order.

        Never omits a step that has not yet been attempted -- it is
        reported with status NOT_ATTEMPTED, never silently dropped, so a
        report always accounts for the whole plan, not just what ran.
        """
        plan, plan_id = self._plan(execution_id)
        executions = self._latest_executions(plan_id)

        entries = []
        for step in plan.steps:
            record = executions.get(step.step_id)
            # execution_id, not plan_id: passed straight through so Commit
            # #9 resolves it exactly as it would for any other caller,
            # whether or not it was built with its own plan_execution_service.
            classification = self._failure_service.classify(execution_id, step.step_id)
            entries.append(self._step_entry(step, record, classification))
        return entries

    def failures(self, execution_id: str) -> list:
        """Every step Commit #9 currently classifies as something other
        than NONE -- both a step that failed on its own and one blocked by
        a dependency -- each with its own reason, verbatim."""
        plan, _plan_id = self._plan(execution_id)
        failures = []
        for step in plan.steps:
            classification = self._failure_service.classify(execution_id, step.step_id)
            if classification.category != NO_FAILURE:
                failures.append(dataclasses.asdict(classification))
        return failures

    def budget(self, execution_id: str) -> dict:
        """execution_id's Commit #10 usage/limits, or {"configured": False}
        when no budget service is wired or none was configured for it."""
        if self._budget_service is None:
            return {"configured": False}
        try:
            usage_and_limits = self._budget_service.snapshot(execution_id)
            remaining = self._budget_service.remaining(execution_id)
            state = self._budget_service.exceeded(execution_id)
        except UnknownExecutionBudgetError:
            return {"configured": False}
        return {
            "configured": True,
            "usage": usage_and_limits["usage"],
            "limits": usage_and_limits["limits"],
            "remaining": remaining,
            "state": state,
        }

    def _checkpoints(self, execution_id: str) -> list:
        if self._checkpoint_service is None:
            return []
        try:
            checkpoint = self._checkpoint_service.latest(execution_id)
        except UnknownCheckpointError:
            return []
        return [
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "execution_id": checkpoint.execution_id,
                "completed_steps": [dict(entry) for entry in checkpoint.completed_steps],
                "current_step": checkpoint.current_step,
                "state": checkpoint.state,
                "created_at": _isoformat(checkpoint.created_at),
            }
        ]

    def timeline(self, execution_id: str) -> list:
        """Every recorded step attempt and checkpoint, ordered by when it
        actually happened -- not by the plan's own declared order."""
        steps = self.steps(execution_id)
        events = []
        for entry in steps:
            if entry["completed_at"] is None:
                continue
            events.append(
                {
                    "type": "step",
                    "step_id": entry["step_id"],
                    "status": entry["status"],
                    "at": entry["completed_at"],
                }
            )
        for checkpoint in self._checkpoints(execution_id):
            events.append(
                {
                    "type": "checkpoint",
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "status": checkpoint["state"],
                    "at": checkpoint["created_at"],
                }
            )
        events.sort(key=lambda event: event["at"])
        return events

    def _status(self, execution_id: str, steps: list) -> str:
        if self._plan_execution_service is not None:
            try:
                return self._plan_execution_service.get(execution_id).status
            except Exception:
                pass

        if any(entry["category"] not in (NO_FAILURE, "DEPENDENCY_FAILURE") for entry in steps):
            return "FAILED"
        if all(entry["status"] == SUCCEEDED for entry in steps):
            return "SUCCEEDED"
        return "IN_PROGRESS"

    def generate(self, execution_id: str) -> dict:
        """The complete, structured, JSON-safe report for execution_id."""
        steps = self.steps(execution_id)

        # Commit #8's own "not making progress" set, split by Commit #9's
        # own reason into "blocked by a dependency" versus "failed on its
        # own" -- reusing both records rather than re-deriving either.
        not_progressing = set(self._dependency_service.blocked_steps(execution_id))
        blocked = {
            entry["step_id"] for entry in steps
            if entry["step_id"] in not_progressing and entry["category"] == "DEPENDENCY_FAILURE"
        }
        failed = {
            entry["step_id"] for entry in steps
            if entry["step_id"] in not_progressing and entry["category"] not in (NO_FAILURE, "DEPENDENCY_FAILURE")
        }
        completed = [entry["step_id"] for entry in steps if entry["status"] == SUCCEEDED]

        return {
            "execution_id": execution_id,
            "status": self._status(execution_id, steps),
            "completed_steps": completed,
            "failed_steps": [entry["step_id"] for entry in steps if entry["step_id"] in failed],
            "blocked_steps": [entry["step_id"] for entry in steps if entry["step_id"] in blocked],
            "budget_usage": self.budget(execution_id),
            "checkpoints": self._checkpoints(execution_id),
            "timings": [
                {
                    "step_id": entry["step_id"],
                    "started_at": entry["started_at"],
                    "completed_at": entry["completed_at"],
                }
                for entry in steps
            ],
            "steps": steps,
            "failures": self.failures(execution_id),
            "timeline": self.timeline(execution_id),
        }
