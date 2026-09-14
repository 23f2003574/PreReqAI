from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import CONSUMPTION_AUDIT_OUTCOMES, AgentTaskRecoveryConsumptionAuditEntry
from .preflight_authorization import LLMAgentTaskRecoveryPreflightAuthorizationService


class InvalidAgentTaskRecoveryConsumptionAuditError(ValueError):
    """Raised when record_attempt()/get()/list() is given invalid
    arguments."""


class AgentTaskRecoveryConsumptionAuditStore(ABC):
    """Raw append-only persistence for AgentTaskRecoveryConsumptionAuditEntry
    records, one growing list per task_id -- the same save()/list_for_task()
    shape backend.agent_task_state_history.AgentTaskTransitionStore and
    this package's own Commit #4 preflight store already establish. There
    is no update() or delete(): an audit entry is never rewritten or
    removed once recorded."""

    @abstractmethod
    def save(self, entry: AgentTaskRecoveryConsumptionAuditEntry) -> AgentTaskRecoveryConsumptionAuditEntry:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryConsumptionAuditStore(AgentTaskRecoveryConsumptionAuditStore):
    """Stores AgentTaskRecoveryConsumptionAuditEntry records in memory,
    for development and testing."""

    def __init__(self):
        self._entries: dict = {}

    def save(self, entry: AgentTaskRecoveryConsumptionAuditEntry) -> AgentTaskRecoveryConsumptionAuditEntry:
        stored = deepcopy(entry)
        self._entries.setdefault(entry.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        entries = self._entries.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.attempted_at)]


class JsonAgentTaskRecoveryConsumptionAuditStore(AgentTaskRecoveryConsumptionAuditStore):
    """Persists AgentTaskRecoveryConsumptionAuditEntry records to a JSON
    file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, entry: AgentTaskRecoveryConsumptionAuditEntry) -> AgentTaskRecoveryConsumptionAuditEntry:
        entries = self.file.read()
        entries.setdefault(entry.task_id, []).append(entry.to_dict())
        self.file.write(entries)
        return deepcopy(entry)

    def list_for_task(self, task_id: str) -> list:
        entries = self.file.read()
        matching = [AgentTaskRecoveryConsumptionAuditEntry.from_dict(data) for data in entries.get(task_id, [])]
        return sorted(matching, key=lambda item: item.attempted_at)


class LLMAgentTaskRecoveryPreflightConsumptionAuditService:
    """Durable, append-only traceability for every Commit #11 consume()
    attempt -- successful, denied, or repeated -- never a parallel
    generic audit framework (Rule: "Do not create a parallel generic
    audit framework"): this reuses THIS package's own already-established
    append-only Store ABC + InMemory/Json shape (Commit #4's own preflight
    store, backend.agent_task_state_history's own transition store)
    rather than inventing a new persistence mechanism, and resolves
    preflight_id/execution_reference by reading Commit #9's own
    authorization service and (when supplied) Commit #11's own
    consumption service -- never re-deriving either fact itself.

    record_attempt() never alters the authorization/preflight/consumption
    records it describes (Rule: "Never alter the authorization/preflight
    decision merely for audit purposes") -- it only ever reads them (to
    resolve preflight_id/execution_reference) and appends its own,
    separate entry.

    get() returns the MOST RECENT entry for one (task_id, authorization_id)
    -- an authorization can legitimately be attempted more than once
    (denied, then later consumed, for instance); list() returns every
    entry ever recorded for task_id, oldest to newest, across every
    authorization_id it has ever had -- the full, append-only trail.
    """

    def __init__(
        self,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        consumption_service=None,
        store: AgentTaskRecoveryConsumptionAuditStore = None,
    ):
        self._authorization_service = (
            authorization_service if authorization_service is not None else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._consumption_service = consumption_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryConsumptionAuditStore()

    def record_attempt(
        self, task_id: str, authorization_id: str, outcome: str, reason: str = None
    ) -> AgentTaskRecoveryConsumptionAuditEntry:
        """Record one consumption attempt for (task_id, authorization_id).
        Always appends a new entry -- never idempotent by design, since
        every distinct attempt (including a repeat of an already-decided
        one) must be independently traceable.

        Raises:
            InvalidAgentTaskRecoveryConsumptionAuditError: If task_id/
                authorization_id is not a non-empty string, or outcome is
                not one of CONSUMPTION_AUDIT_OUTCOMES
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")
        if outcome not in CONSUMPTION_AUDIT_OUTCOMES:
            raise InvalidAgentTaskRecoveryConsumptionAuditError(
                f"outcome {outcome!r} is not one of {sorted(CONSUMPTION_AUDIT_OUTCOMES)}"
            )

        preflight_id = None
        authorization = self._authorization_service.get(task_id, authorization_id)
        if authorization is not None:
            preflight_id = authorization.preflight_id

        execution_reference = None
        if self._consumption_service is not None:
            consumption = self._consumption_service.get(task_id, authorization_id)
            if consumption is not None:
                execution_reference = consumption.consumption_id

        entry = AgentTaskRecoveryConsumptionAuditEntry(
            task_id=task_id, authorization_id=authorization_id, preflight_id=preflight_id,
            outcome=outcome, reason=reason, execution_reference=execution_reference,
            attempted_at=datetime.now(timezone.utc),
        )
        return self._store.save(entry)

    def get(self, task_id: str, authorization_id: str):
        """The most recently recorded attempt for (task_id,
        authorization_id), or None if none was ever recorded."""
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")
        matching = [entry for entry in self.list(task_id) if entry.authorization_id == authorization_id]
        return matching[-1] if matching else None

    def list(self, task_id: str) -> list:
        """Every attempt ever recorded for task_id, across every
        authorization_id, oldest to newest."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryConsumptionAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
