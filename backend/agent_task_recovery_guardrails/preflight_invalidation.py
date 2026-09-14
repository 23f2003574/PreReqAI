from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryPreflightInvalidation, AgentTaskRecoveryPreflightInvalidationResult
from .preflight_freshness import LLMAgentTaskRecoveryPreflightFreshnessService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore

_EXPLICIT_REASON = "explicitly invalidated"


class InvalidAgentTaskRecoveryPreflightInvalidationError(ValueError):
    """Raised when invalidate()/invalidate_if_stale() is given invalid
    arguments."""


class AgentTaskRecoveryPreflightInvalidationStore(ABC):
    """Raw persistence for the one current AgentTaskRecoveryPreflightInvalidation
    record per preflight_id -- the same single-current-record-per-key
    shape backend.agent_task_queue_dead_letter.DeadLetterStore already
    uses for a comparable "is this thing still usable" fact. There is no
    update() or delete(): once a preflight_id has an invalidation record,
    it is never rewritten or removed."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightInvalidation) -> AgentTaskRecoveryPreflightInvalidation:
        ...

    @abstractmethod
    def get(self, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightInvalidation]:
        ...


class InMemoryAgentTaskRecoveryPreflightInvalidationStore(AgentTaskRecoveryPreflightInvalidationStore):
    """Stores AgentTaskRecoveryPreflightInvalidation records in memory,
    for development and testing."""

    def __init__(self):
        self._records: dict = {}

    def save(self, record: AgentTaskRecoveryPreflightInvalidation) -> AgentTaskRecoveryPreflightInvalidation:
        stored = deepcopy(record)
        self._records[record.preflight_id] = stored
        return deepcopy(stored)

    def get(self, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightInvalidation]:
        record = self._records.get(preflight_id)
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryPreflightInvalidationStore(AgentTaskRecoveryPreflightInvalidationStore):
    """Persists AgentTaskRecoveryPreflightInvalidation records to a JSON
    file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryPreflightInvalidation) -> AgentTaskRecoveryPreflightInvalidation:
        records = self.file.read()
        records[record.preflight_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightInvalidation]:
        records = self.file.read()
        data = records.get(preflight_id)
        return AgentTaskRecoveryPreflightInvalidation.from_dict(data) if data is not None else None


class LLMAgentTaskRecoveryPreflightInvalidationService:
    """Identifies and marks stored Commit #4 preflights unusable when the
    evidence they depend on changes -- kept distinct from Commit #5's own
    freshness detection (Rule: "Keep this distinct from freshness
    checking: freshness detects staleness; invalidation changes the
    stored preflight's usable status"): invalidate_if_stale() is the one
    and only bridge between the two, calling Commit #5's own check() and
    never re-deriving any part of its own comparisons a second way (Rule:
    "No duplicate freshness logic").

    Never deletes or rewrites the original preflight (Rule: "Never delete
    the original preflight"; "preserve the original preflight but mark it
    unusable"): every method here only ever reads through Commit #4's own
    LLMAgentTaskRecoveryPreflightStore.get() and writes a SEPARATE
    AgentTaskRecoveryPreflightInvalidation record, the same "mark
    unusable via an additive record, never by rewriting the original"
    discipline backend.agent_task_queue_dead_letter.DeadLetterEntry
    already establishes for a comparable case -- Commit #4's own append-
    only history (Rule: "Preserve preflight history"; "history retains
    the original record") is therefore completely unaffected by anything
    this service does.

    Idempotent by preflight_id (Rule: "Already-invalid preflights remain
    idempotently invalid"; "repeated invalidation is idempotent"): both
    invalidate()/invalidate_if_stale() check the underlying
    AgentTaskRecoveryPreflightInvalidationStore for an existing record
    before ever creating a new one -- the same "check store.get() first,
    return the existing entry unchanged" convention backend.
    agent_task_queue_dead_letter.LLMAgentTaskDeadLetterService.dead_letter()
    already establishes. A second call with a different `reason` still
    returns the FIRST invalidation's own reason unchanged -- the first
    recorded reason is authoritative, never silently replaced.

    invalidate_if_stale() never invalidates a fresh preflight (Rule: "Do
    not invalidate a fresh preflight"): it only ever calls invalidate()
    when Commit #5's own check() reports is_fresh=False, with `reason`
    built directly from that same check's own stale_reasons (never a
    separately invented explanation).

    Never touches authoritative task state (Rule: "Never mutate
    authoritative task state"): neither method here calls anything from
    backend.agent_task_lifecycle/agent_task_events, only Commit #4's own
    preflight store and Commit #5's own freshness service.

    Missing preflight handled cleanly (Rule, via the Tests list): a
    task_id with no stored preflight at all is reported as
    preflight_id=None/is_invalid=False, never an error and never a
    fabricated invalidation of something that does not exist.
    """

    def __init__(
        self,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        freshness_service: LLMAgentTaskRecoveryPreflightFreshnessService = None,
        invalidation_store: AgentTaskRecoveryPreflightInvalidationStore = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._freshness_service = (
            freshness_service if freshness_service is not None else LLMAgentTaskRecoveryPreflightFreshnessService()
        )
        self._invalidation_store = (
            invalidation_store if invalidation_store is not None else InMemoryAgentTaskRecoveryPreflightInvalidationStore()
        )

    def invalidate(self, task_id: str, reason: str = None) -> AgentTaskRecoveryPreflightInvalidationResult:
        """Explicitly mark task_id's current stored preflight unusable.
        Idempotent: an already-invalid preflight is reported unchanged,
        with its own original reason, rather than being re-invalidated.

        Raises:
            InvalidAgentTaskRecoveryPreflightInvalidationError: If task_id
                is not a non-empty string, or reason is given and is not
                a non-empty string
        """
        self._require_text(task_id)
        if reason is not None:
            self._require_text(reason, field_name="reason")

        preflight = self._preflight_store.get(task_id)
        if preflight is None:
            return self._no_preflight_result(task_id)

        return self._invalidate_preflight(task_id, preflight, reason or _EXPLICIT_REASON)

    def invalidate_if_stale(self, task_id: str) -> AgentTaskRecoveryPreflightInvalidationResult:
        """Invalidate task_id's current stored preflight only if Commit
        #5's own freshness check reports it stale. A fresh preflight is
        left alone (Rule: "Do not invalidate a fresh preflight").

        An already-invalidated preflight (whether by a prior call to this
        same method, or by an explicit invalidate() call for a reason
        Commit #5's own freshness check has no way to see, e.g. an
        operator's own manual judgment) is reported as still invalid
        BEFORE freshness is even consulted -- never re-validated back to
        "not invalid" merely because it now happens to look fresh again
        (an explicit invalidation is a standing decision, not something a
        later freshness check can silently override).

        Raises:
            InvalidAgentTaskRecoveryPreflightInvalidationError: If task_id
                is not a non-empty string
        """
        self._require_text(task_id)

        preflight = self._preflight_store.get(task_id)
        if preflight is None:
            return self._no_preflight_result(task_id)

        already_invalid = self._invalidation_store.get(preflight.preflight_id)
        if already_invalid is not None:
            return AgentTaskRecoveryPreflightInvalidationResult(
                task_id=task_id, preflight_id=preflight.preflight_id, is_invalid=True,
                invalidated_at=already_invalid.invalidated_at, reason=already_invalid.reason,
                previous_decision=already_invalid.previous_decision,
            )

        freshness = self._freshness_service.check(task_id, preflight=preflight)
        if freshness.is_fresh:
            return AgentTaskRecoveryPreflightInvalidationResult(
                task_id=task_id, preflight_id=preflight.preflight_id, is_invalid=False,
                invalidated_at=None, reason=None, previous_decision=None,
            )

        reason = "stale: " + "; ".join(freshness.stale_reasons)
        return self._invalidate_preflight(task_id, preflight, reason)

    def _invalidate_preflight(self, task_id, preflight, reason: str) -> AgentTaskRecoveryPreflightInvalidationResult:
        existing = self._invalidation_store.get(preflight.preflight_id)
        if existing is not None:
            return AgentTaskRecoveryPreflightInvalidationResult(
                task_id=task_id, preflight_id=preflight.preflight_id, is_invalid=True,
                invalidated_at=existing.invalidated_at, reason=existing.reason,
                previous_decision=existing.previous_decision,
            )

        record = AgentTaskRecoveryPreflightInvalidation(
            task_id=task_id,
            preflight_id=preflight.preflight_id,
            reason=reason,
            previous_decision=preflight.decision,
            invalidated_at=datetime.now(timezone.utc),
        )
        saved = self._invalidation_store.save(record)

        return AgentTaskRecoveryPreflightInvalidationResult(
            task_id=task_id, preflight_id=preflight.preflight_id, is_invalid=True,
            invalidated_at=saved.invalidated_at, reason=saved.reason, previous_decision=saved.previous_decision,
        )

    @staticmethod
    def _no_preflight_result(task_id: str) -> AgentTaskRecoveryPreflightInvalidationResult:
        return AgentTaskRecoveryPreflightInvalidationResult(
            task_id=task_id, preflight_id=None, is_invalid=False,
            invalidated_at=None, reason=None, previous_decision=None,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightInvalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
