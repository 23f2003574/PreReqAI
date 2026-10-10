import hashlib
import json
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import (
    CORRUPTED,
    MISSING,
    UNVERIFIABLE,
    VALID,
    AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord,
    AgentTaskRecoveryPreflightDependencySnapshotIntegrityResult,
)
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError(ValueError):
    """Raised when compute()/verify() is given invalid arguments, or
    compute() is asked for a snapshot that does not exist."""


class AgentTaskRecoveryPreflightDependencySnapshotIntegrityStore(ABC):
    """Raw, write-once persistence for the one baseline
    AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord per
    (task_id, snapshot_id). No update()/delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord
    ) -> AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord:
        ...

    @abstractmethod
    def get(self, task_id: str, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord]:
        ...


class InMemoryAgentTaskRecoveryPreflightDependencySnapshotIntegrityStore(AgentTaskRecoveryPreflightDependencySnapshotIntegrityStore):
    """Stores integrity baseline records in memory, for development and
    testing."""

    def __init__(self):
        self._records: dict = {}

    def save(self, record):
        stored = deepcopy(record)
        self._records[(record.task_id, record.snapshot_id)] = stored
        return deepcopy(stored)

    def get(self, task_id, snapshot_id):
        record = self._records.get((task_id, snapshot_id))
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryPreflightDependencySnapshotIntegrityStore(AgentTaskRecoveryPreflightDependencySnapshotIntegrityStore):
    """Persists integrity baseline records to a JSON file, keyed by
    "task_id::snapshot_id"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, snapshot_id: str) -> str:
        return f"{task_id}::{snapshot_id}"

    def save(self, record):
        records = self.file.read()
        records[self._key(record.task_id, record.snapshot_id)] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, task_id, snapshot_id):
        data = self.file.read().get(self._key(task_id, snapshot_id))
        return AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord.from_dict(data) if data is not None else None


class LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService:
    """Verifies that a persisted Commit #1 snapshot has not silently
    changed since it was first trusted -- never a generic integrity
    framework (Rule): compute() reuses this repository's own established
    canonical-hash recipe verbatim (json.dumps(..., sort_keys=True,
    default=str) then hashlib.sha256(...).hexdigest(), the exact
    convention backend.llm.response_cache/backend.llm.tool_idempotency/
    backend.agent_capability_execution._reference_for() already use for
    "a short string identifies content without embedding it").

    Trust-on-first-use baseline, not a second snapshot store (Rule: "do
    not invent a generic integrity framework"): verify() records the
    FIRST computed integrity_value for a (task_id, snapshot_id) as its
    durable baseline (a small, write-once record -- never a copy of the
    snapshot itself), then compares every later call's freshly recomputed
    value against that same baseline. A mismatch means the underlying
    persisted snapshot content, its identity/timestamp metadata, or (when
    a version_service is configured) its own version binding no longer
    agrees with what was first trusted.

    Bound to the exact task/preflight/snapshot/version (Rule): the
    canonical hash input is {task_id, preflight_id, snapshot_id,
    captured_at, version, dependencies} -- every one of those fields
    participates, so tampering with ANY of them (not just the dependency
    list) is caught the same way. version is resolved via an optional
    Commit #3 version_service (list_versions() filtered to this exact
    snapshot_id); more than one version number bound to the same
    snapshot_id is reported as its own reason, distinct from a plain hash
    mismatch.

    Never mutates the snapshot itself, never executes/authorizes/
    reschedules/modifies recovery (Rule): only this class's own small
    baseline store is ever written; Commit #1's own snapshot store is
    only ever read.

    Deterministic (Rule): compute() is a pure function of a snapshot's
    already-immutable content plus its resolved version -- calling it
    twice for an unchanged snapshot always returns the identical value.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        version_service=None,
        store: AgentTaskRecoveryPreflightDependencySnapshotIntegrityStore = None,
    ):
        """
        Args:
            version_service: Optional Commit #3
                LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService
                (duck-typed, only its list_versions() is called).
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._version_service = version_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightDependencySnapshotIntegrityStore()

    def compute(self, task_id: str, snapshot_id: str) -> str:
        """The current canonical integrity_value for task_id's exact
        snapshot_id -- a pure read, no baseline recorded.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError:
                If task_id/snapshot_id is not a non-empty string, or no
                such snapshot is recorded for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )
        version, _ = self._resolve_version(snapshot)
        return self._hash(snapshot, version)

    def verify(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotIntegrityResult:
        """Verify task_id's exact snapshot_id against its own recorded
        baseline, establishing that baseline now if this is the first
        verify() ever run for it.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            return self._result(task_id, snapshot_id, None, None, MISSING, None, ("no such snapshot is recorded",))

        try:
            version, version_issue = self._resolve_version(snapshot)
            current_value = self._hash(snapshot, version)
            reasons = [version_issue] if version_issue else []

            baseline = self._store.get(task_id, snapshot_id)
            if baseline is None:
                self._store.save(
                    AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord(
                        task_id=task_id, snapshot_id=snapshot_id, integrity_value=current_value,
                        recorded_at=self._now(),
                    )
                )
            elif baseline.integrity_value != current_value:
                reasons.append("snapshot content/metadata no longer matches its recorded integrity value")

            status = CORRUPTED if reasons else VALID
            return self._result(task_id, snapshot_id, snapshot.preflight_id, version, status, current_value, tuple(reasons))
        except Exception as error:
            return self._result(
                task_id, snapshot_id, snapshot.preflight_id, None, UNVERIFIABLE, None,
                (f"integrity could not be verified: {error}",),
            )

    def _resolve_version(self, snapshot) -> tuple:
        if self._version_service is None:
            return None, None
        matches = sorted(
            {
                entry.version
                for entry in self._version_service.list_versions(snapshot.task_id, snapshot.preflight_id)
                if entry.snapshot_id == snapshot.snapshot_id
            }
        )
        if len(matches) > 1:
            return None, f"snapshot is inconsistently bound to multiple version numbers: {matches}"
        return (matches[0] if matches else None), None

    @staticmethod
    def _hash(snapshot, version: Optional[int]) -> str:
        canonical = json.dumps(
            {
                "task_id": snapshot.task_id,
                "preflight_id": snapshot.preflight_id,
                "snapshot_id": snapshot.snapshot_id,
                "captured_at": snapshot.captured_at,
                "version": version,
                "dependencies": sorted(
                    ({"dependency_task_id": e.dependency_task_id, "state": e.state} for e in snapshot.dependencies),
                    key=lambda entry: entry["dependency_task_id"],
                ),
            },
            sort_keys=True, default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _result(self, task_id, snapshot_id, preflight_id, version, status, integrity_value, reasons):
        return AgentTaskRecoveryPreflightDependencySnapshotIntegrityResult(
            task_id=task_id, snapshot_id=snapshot_id, preflight_id=preflight_id, version=version,
            status=status, valid=status == VALID, integrity_value=integrity_value, reasons=reasons,
            verified_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError(
                f"{field_name} is required and must be a non-empty string"
            )
