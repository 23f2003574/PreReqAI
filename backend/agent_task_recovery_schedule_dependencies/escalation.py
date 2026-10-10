from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService
from backend.storage import AtomicJsonFile

from .timeout import TIMED_OUT, LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService

# The event_type this service emits through backend.agent_task_events'
# own, already-existing LLMAgentTaskEventService.emit() when one is
# supplied -- a new, but consistent, addition to that module's own
# deliberately-open, "documented, not enforced" event_type vocabulary
# (Rule: "Use existing task/recovery escalation or event mechanisms if
# present"), the same way Commit #4-of-agent_task_events' own
# CORRELATION_ESTABLISHED extended it for a genuinely new concept rather
# than inventing a second event bus.
DEPENDENCY_WAIT_ESCALATED_EVENT_TYPE = "dependency_wait_escalated"


class InvalidAgentTaskRecoveryScheduleDependencyEscalationError(ValueError):
    """Raised when assess()/escalate() is given invalid arguments, names
    a schedule that does not exist for task_id, or escalate() is asked
    to escalate a schedule that does not currently meet the escalation
    threshold."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleEscalationResult:
    """assess()'s read-only, explainable verdict, and escalate()'s own
    return value once it has acted (Rule: "Distinguish normal waiting
    from genuinely escalation-worthy blocking").

    should_escalate is exactly `timeout_state == TIMED_OUT and not
    already_escalated` -- Rule: "Escalate only when existing dependency
    evidence meets an existing timeout/policy threshold": the threshold
    is Commit #6's own already-established TIMED_OUT determination,
    reused verbatim, never a second, separately-tuned escalation
    threshold.

    dependency_evidence/wait_duration/attempt_count/remaining_attempts/
    policy_decision/policy_reasons are exactly Rule's own "dependency
    evidence, wait duration, attempts, and applicable policy/risk
    context where already available" -- each sourced from an existing
    collaborator (Commit #6's own check(), an optional Commit #9-of-
    agent_task_queue_retry_scheduler retry_scheduler, an optional
    Commit #4-of-agent_task_recovery_guardrails preflight_store), never
    recomputed a second way; each is None/() when its own optional
    source collaborator was not supplied.
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    should_escalate: bool
    already_escalated: bool
    timeout_state: str
    dependency_evidence: tuple
    wait_duration: Optional[timedelta]
    attempt_count: Optional[int]
    remaining_attempts: Optional[int]
    policy_decision: Optional[str]
    policy_reasons: tuple
    reason: str
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleEscalation:
    """One immutable, append-only entry recording that task_id's exact
    schedule_id was escalated -- never updated or deleted once recorded
    (Rule: "Preserve the original schedule and dependency history"),
    the same append-only discipline this package's own Commit #2/#3/#5
    already establish. Never itself changes the underlying schedule (no
    cancel(), no schedule()) -- escalation is purely an additive marker
    plus, optionally, an existing-mechanism event (Rule: "Escalation
    must feed back into normal recovery decision/review flow rather
    than directly forcing execution")."""

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    reason: str
    dependency_evidence: tuple
    wait_duration_seconds: Optional[float]
    attempt_count: Optional[int]
    remaining_attempts: Optional[int]
    policy_decision: Optional[str]
    policy_reasons: tuple
    escalated_at: datetime
    escalation_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["escalated_at"] = self.escalated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleEscalation":
        payload = dict(data)
        value = payload.get("escalated_at")
        if isinstance(value, str):
            payload["escalated_at"] = datetime.fromisoformat(value)
        for key in ("dependency_evidence", "policy_reasons"):
            if key in payload and payload[key] is not None:
                payload[key] = tuple(payload[key])
        return cls(**payload)


class AgentTaskRecoveryScheduleEscalationStore(ABC):
    """Append-only persistence for AgentTaskRecoveryScheduleEscalation
    records -- the same save()/list_for_-- split this package's own
    Commit #2/#3/#5 stores already establish. There is no update() or
    delete()."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleEscalation) -> AgentTaskRecoveryScheduleEscalation:
        ...

    @abstractmethod
    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleEscalationStore(AgentTaskRecoveryScheduleEscalationStore):
    """Stores dependency-wait escalations in memory, for development and
    testing."""

    def __init__(self):
        self._by_schedule: dict = {}

    def save(self, record: AgentTaskRecoveryScheduleEscalation) -> AgentTaskRecoveryScheduleEscalation:
        stored = deepcopy(record)
        self._by_schedule.setdefault((record.task_id, record.schedule_id), []).append(stored)
        return deepcopy(stored)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        entries = self._by_schedule.get((task_id, schedule_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.escalated_at)]

    def list_for_task(self, task_id: str) -> list:
        entries = [entry for (t, _), entries in self._by_schedule.items() if t == task_id for entry in entries]
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.escalated_at)]


class JsonAgentTaskRecoveryScheduleEscalationStore(AgentTaskRecoveryScheduleEscalationStore):
    """Persists dependency-wait escalations to a JSON file, keyed by
    f"{task_id}::{schedule_id}"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, schedule_id: str) -> str:
        return f"{task_id}::{schedule_id}"

    def save(self, record: AgentTaskRecoveryScheduleEscalation) -> AgentTaskRecoveryScheduleEscalation:
        records = self.file.read()
        key = self._key(record.task_id, record.schedule_id)
        records.setdefault(key, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        records = self.file.read()
        matching = [
            AgentTaskRecoveryScheduleEscalation.from_dict(data)
            for data in records.get(self._key(task_id, schedule_id), [])
        ]
        return sorted(matching, key=lambda item: item.escalated_at)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        prefix = f"{task_id}::"
        matching = [
            AgentTaskRecoveryScheduleEscalation.from_dict(data)
            for key, entries in records.items() if key.startswith(prefix)
            for data in entries
        ]
        return sorted(matching, key=lambda item: item.escalated_at)


class LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService:
    """Surfaces a persistently dependency-blocked schedule for policy/
    human attention instead of leaving it waiting indefinitely -- never
    a second escalation platform (Rule: "Do not invent a new escalation
    framework" / "implement only the smallest repository-native state
    transition needed"): the escalation THRESHOLD is entirely Commit
    #6's own already-established check() (TIMED_OUT, never a second,
    separately-tuned formula), and the only write anywhere in this class
    is this module's own small, append-only escalation-marker store plus
    an OPTIONAL existing-mechanism event via backend.agent_task_events'
    own already-existing LLMAgentTaskEventService.emit() -- never
    backend.agent_policy_risk_escalation's own LLMAgentRiskEscalationService
    (that service's own identity space, request_id against Commit #5-of-
    agent_policy_risk_approval's own ApprovalRequirement, is a different
    domain entirely from this package's own task_id/schedule_id -- Rule:
    "reuse existing ... mechanisms" means reusing the SHAPE and the
    EXISTING emit() mechanism, never force-fitting a mismatched identity
    into a tightly-coupled service, the same "reuse data shapes/hooks,
    never the tightly-coupled service" precedent already established for
    every other cross-domain reuse in this whole task family).

    assess() never mutates anything (Rule): every collaborator it calls
    -- Commit #6's own timeout check(), an optional Commit #9-of-
    agent_task_queue_retry_scheduler retry_scheduler.resolve_eligibility()
    (read-only, "attempts"), an optional Commit #4-of-agent_task_recovery_
    guardrails preflight_store.history() lookup (read-only, "applicable
    policy/risk context") -- is itself read-only.

    escalate() only ever succeeds when assess() itself currently reports
    should_escalate (Rule: "Escalate only when ... meets an existing
    timeout/policy threshold"), and is idempotent (Rule: "Make repeated
    escalation idempotent"): a schedule already escalated is returned
    unchanged via assess()'s own already_escalated=True view, no new
    store row, no duplicate event. It never touches Commit #1-of-
    agent_task_recovery_scheduling's own schedule()/cancel() at all (Rule:
    "Preserve the original schedule" / "Never execute recovery or bypass
    authorization/guardrails" / "feed back into normal recovery decision/
    review flow rather than directly forcing execution") -- an escalated
    schedule's own dispatch eligibility is governed entirely by whatever
    already made it TIMED_OUT in the first place (Commit #6's own
    check(), if a caller separately wired that into validation.py's own
    hook), never by escalation itself granting or revoking anything.
    """

    def __init__(
        self,
        timeout_service: LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        retry_scheduler=None,
        preflight_store=None,
        event_service=None,
        store: AgentTaskRecoveryScheduleEscalationStore = None,
    ):
        """
        Args:
            timeout_service: Commit #6's own timeout service -- the sole
                source of the escalation threshold. Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService
                built over scheduling_service (no dependency_service/
                blocking_service of its own -- always reports NOT_WAITING,
                so nothing would ever meet the threshold; pass the real,
                wired instance for this service to ever escalate
                anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used only
                to build a default timeout_service when none is given.
            retry_scheduler: No default. When given, its own
                resolve_eligibility(task_id).attempt_count/
                remaining_attempts are attached to every result as
                "attempts" context; omitted, both stay None.
            preflight_store: No default. When given, the original
                Commit #4-of-agent_task_recovery_guardrails preflight's
                own decision/blocking_reasons/warnings (looked up by the
                schedule's own preflight_id) are attached as
                policy_decision/policy_reasons; omitted, both stay
                empty/None.
            event_service: No default. When given, a genuine escalate()
                also emits one DEPENDENCY_WAIT_ESCALATED_EVENT_TYPE event
                via its own existing emit() (Rule: "Use existing task/
                recovery escalation or event mechanisms if present");
                omitted, no event is emitted.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryScheduleEscalationStore.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._timeout_service = (
            timeout_service
            if timeout_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
                scheduling_service=self._scheduling_service
            )
        )
        self._retry_scheduler = retry_scheduler
        self._preflight_store = preflight_store
        self._event_service = event_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleEscalationStore()

    def assess(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleEscalationResult:
        """Read-only escalation-worthiness verdict for task_id's exact
        schedule_id, re-evaluated fresh every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyEscalationError:
                If task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        if self._scheduling_service.get(task_id, schedule_id) is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyEscalationError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        timeout_result = self._timeout_service.check(task_id, schedule_id, now=now)

        existing = self._latest(task_id, schedule_id)
        already_escalated = existing is not None

        wait_duration = None
        if timeout_result.wait_started_at is not None:
            wait_duration = now - timeout_result.wait_started_at

        attempt_count = remaining_attempts = None
        if self._retry_scheduler is not None:
            eligibility = self._retry_scheduler.resolve_eligibility(task_id, now=now)
            attempt_count = eligibility.attempt_count
            remaining_attempts = eligibility.remaining_attempts

        policy_decision = None
        policy_reasons: tuple = ()
        if self._preflight_store is not None and timeout_result.preflight_id:
            preflight = self._find_preflight(task_id, timeout_result.preflight_id)
            if preflight is not None:
                policy_decision = preflight.decision
                policy_reasons = tuple(preflight.blocking_reasons) + tuple(preflight.warnings)

        should_escalate = timeout_result.state == TIMED_OUT and not already_escalated

        if already_escalated:
            reason = f"already escalated at {existing.escalated_at.isoformat()}"
        elif timeout_result.state == TIMED_OUT:
            reason = f"dependency wait has met the escalation threshold: {timeout_result.reason}"
        else:
            reason = f"escalation threshold not met: {timeout_result.reason}"

        return AgentTaskRecoveryScheduleEscalationResult(
            task_id=task_id, schedule_id=schedule_id, preflight_id=timeout_result.preflight_id,
            should_escalate=should_escalate, already_escalated=already_escalated,
            timeout_state=timeout_result.state, dependency_evidence=timeout_result.dependency_evidence,
            wait_duration=wait_duration, attempt_count=attempt_count, remaining_attempts=remaining_attempts,
            policy_decision=policy_decision, policy_reasons=policy_reasons, reason=reason, checked_at=now,
        )

    def escalate(
        self, task_id: str, schedule_id: str, reason: Optional[str] = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleEscalationResult:
        """Escalate task_id's exact schedule_id, if it currently meets
        the escalation threshold. Idempotent: a schedule already
        escalated is returned unchanged, no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyEscalationError:
                If task_id/schedule_id is not a non-empty string, reason
                is given and is not a string, now is given and is not a
                datetime, or the schedule does not currently meet the
                escalation threshold
        """
        if reason is not None and not isinstance(reason, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyEscalationError("reason must be a string when given")
        now = self._resolve_now(now)
        assessment = self.assess(task_id, schedule_id, now=now)

        if assessment.already_escalated:
            return assessment

        if not assessment.should_escalate:
            raise InvalidAgentTaskRecoveryScheduleDependencyEscalationError(
                f"schedule {schedule_id!r} does not currently meet the escalation threshold: {assessment.reason}"
            )

        record = AgentTaskRecoveryScheduleEscalation(
            task_id=task_id, schedule_id=schedule_id, preflight_id=assessment.preflight_id,
            reason=reason if reason is not None else assessment.reason,
            dependency_evidence=assessment.dependency_evidence,
            wait_duration_seconds=assessment.wait_duration.total_seconds() if assessment.wait_duration else None,
            attempt_count=assessment.attempt_count, remaining_attempts=assessment.remaining_attempts,
            policy_decision=assessment.policy_decision, policy_reasons=assessment.policy_reasons, escalated_at=now,
        )
        self._store.save(record)

        if self._event_service is not None:
            self._event_service.emit(
                task_id, DEPENDENCY_WAIT_ESCALATED_EVENT_TYPE,
                payload={"schedule_id": schedule_id, "preflight_id": assessment.preflight_id, "reason": record.reason},
            )

        return self.assess(task_id, schedule_id, now=now)

    def get_history(self, task_id: str, schedule_id: str) -> list:
        """Every escalation ever recorded for task_id's exact
        schedule_id, oldest first -- never mutated or trimmed (Rule:
        "Preserve ... dependency history")."""
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        return self._store.list_for_schedule(task_id, schedule_id)

    def _latest(self, task_id: str, schedule_id: str):
        history = self.get_history(task_id, schedule_id)
        return history[-1] if history else None

    def _find_preflight(self, task_id: str, preflight_id: str):
        for record in self._preflight_store.history(task_id):
            if record.preflight_id == preflight_id:
                return record
        return None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyEscalationError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyEscalationError("now must be a datetime when given")
        return now
