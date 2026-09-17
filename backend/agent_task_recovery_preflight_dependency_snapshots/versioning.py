from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryPreflightDependencySnapshot, AgentTaskRecoveryPreflightDependencySnapshotVersion
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(ValueError):
    """Raised when create_version()/get_version()/latest_version()/
    list_versions() is given invalid arguments, create_version() is given
    a snapshot that does not belong to the exact task_id/preflight_id, or
    get_version() names a version that does not exist."""


class AgentTaskRecoveryPreflightDependencySnapshotVersionCollisionError(ValueError):
    """Raised when a version record's own (task_id, preflight_id,
    version) triple already exists in the store -- Rule: "Reject
    accidental overwrites/version collisions". Never raised through the
    ordinary create_version() path (which always assigns the next free
    number itself); only reachable via a direct, mis-numbered save()."""


class AgentTaskRecoveryPreflightDependencySnapshotVersionStore(ABC):
    """Raw persistence for AgentTaskRecoveryPreflightDependencySnapshotVersion
    records, indexed by (task_id, preflight_id) -- the only lookup key
    this package ever needs (a specific version is found by filtering the
    already-small per-preflight list, the same "list then filter" shape
    backend.agent_policy_versioning.LLMAgentPolicyVersionService already
    uses). No update()/delete(): a version, once recorded, is never
    rewritten (Rule: "Preserve every snapshot immutably")."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshotVersion
    ) -> AgentTaskRecoveryPreflightDependencySnapshotVersion:
        ...

    @abstractmethod
    def list_for_preflight(self, task_id: str, preflight_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryPreflightDependencySnapshotVersionStore(AgentTaskRecoveryPreflightDependencySnapshotVersionStore):
    """Stores AgentTaskRecoveryPreflightDependencySnapshotVersion records
    in memory, for development and testing."""

    def __init__(self):
        self._by_preflight: dict = {}

    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshotVersion
    ) -> AgentTaskRecoveryPreflightDependencySnapshotVersion:
        key = (record.task_id, record.preflight_id)
        entries = self._by_preflight.setdefault(key, [])
        if any(entry.version == record.version for entry in entries):
            raise AgentTaskRecoveryPreflightDependencySnapshotVersionCollisionError(
                f"version {record.version} already recorded for task_id {record.task_id!r}, "
                f"preflight_id {record.preflight_id!r}"
            )
        stored = deepcopy(record)
        entries.append(stored)
        return deepcopy(stored)

    def list_for_preflight(self, task_id: str, preflight_id: str) -> list:
        entries = self._by_preflight.get((task_id, preflight_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.version)]


class JsonAgentTaskRecoveryPreflightDependencySnapshotVersionStore(AgentTaskRecoveryPreflightDependencySnapshotVersionStore):
    """Persists AgentTaskRecoveryPreflightDependencySnapshotVersion
    records to a JSON file, keyed by "task_id::preflight_id"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, preflight_id: str) -> str:
        return f"{task_id}::{preflight_id}"

    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshotVersion
    ) -> AgentTaskRecoveryPreflightDependencySnapshotVersion:
        records = self.file.read()
        key = self._key(record.task_id, record.preflight_id)
        entries = records.setdefault(key, [])
        if any(entry.get("version") == record.version for entry in entries):
            raise AgentTaskRecoveryPreflightDependencySnapshotVersionCollisionError(
                f"version {record.version} already recorded for task_id {record.task_id!r}, "
                f"preflight_id {record.preflight_id!r}"
            )
        entries.append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_preflight(self, task_id: str, preflight_id: str) -> list:
        entries = self.file.read().get(self._key(task_id, preflight_id), [])
        matching = [AgentTaskRecoveryPreflightDependencySnapshotVersion.from_dict(data) for data in entries]
        return sorted(matching, key=lambda item: item.version)


class LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService:
    """Numbers Commit #1 snapshots monotonically per (task_id,
    preflight_id), so a caller can reference a precise dependency-state
    revision ("version 3") instead of an ambiguous, unqualified snapshot
    -- never a second snapshot store (Rule: "Reuse #1-#2 ... do not
    invent a generic version-control system"): create_version() never
    copies a snapshot's own content, only records a small pointer to its
    already-immutable snapshot_id; get_version() resolves that pointer
    straight back through Commit #1's own
    LLMAgentTaskRecoveryPreflightDependencySnapshotService.get().

    Monotonic, deterministic numbering (Rule): version = `len(existing) +
    1`, the same convention backend.agent_policy_versioning.
    LLMAgentPolicyVersionService already establishes -- list_versions()
    is always sorted by version ascending, so latest_version() (the last
    entry) is a pure, deterministic function of what has been recorded so
    far, never insertion order or wall-clock ties.

    Idempotent by snapshot_id (Rule: "Reject accidental overwrites/
    version collisions"): calling create_version() again with a snapshot
    whose snapshot_id is ALREADY recorded for this exact (task_id,
    preflight_id) returns that existing version record unchanged, rather
    than minting a second version number for identical content. A version
    number itself, once recorded, can never be overwritten -- the
    underlying store's own save() rejects a duplicate (task_id,
    preflight_id, version) triple outright (defensive; unreachable
    through this class's own ordinary create_version() path).

    Bound to the exact preflight (Rule: "Bind each version to the exact
    preflight and creation context"): create_version() rejects a snapshot
    whose own task_id/preflight_id does not match the task_id/preflight_id
    it was called with.

    No scheduling/authorization/recovery side effects (Rule): this class
    holds no reference to anything that could cause one.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        store: AgentTaskRecoveryPreflightDependencySnapshotVersionStore = None,
    ):
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightDependencySnapshotVersionStore()

    def create_version(
        self, task_id: str, preflight_id: str, snapshot: AgentTaskRecoveryPreflightDependencySnapshot
    ) -> AgentTaskRecoveryPreflightDependencySnapshotVersion:
        """Record snapshot as the next version for (task_id,
        preflight_id). Idempotent: a snapshot_id already versioned here
        returns its existing version record unchanged.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError:
                If task_id/preflight_id is not a non-empty string,
                snapshot is not an AgentTaskRecoveryPreflightDependency
                Snapshot, or snapshot's own task_id/preflight_id does not
                match the ones given
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        if not isinstance(snapshot, AgentTaskRecoveryPreflightDependencySnapshot):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(
                "snapshot must be an AgentTaskRecoveryPreflightDependencySnapshot"
            )
        if snapshot.task_id != task_id or snapshot.preflight_id != preflight_id:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(
                f"snapshot {snapshot.snapshot_id!r} does not belong to task_id {task_id!r} / "
                f"preflight_id {preflight_id!r}"
            )

        existing = self.list_versions(task_id, preflight_id)
        for entry in existing:
            if entry.snapshot_id == snapshot.snapshot_id:
                return entry

        record = AgentTaskRecoveryPreflightDependencySnapshotVersion(
            task_id=task_id, preflight_id=preflight_id, version=len(existing) + 1,
            snapshot_id=snapshot.snapshot_id, created_at=datetime.now(timezone.utc),
        )
        return self._store.save(record)

    def get_version(self, task_id: str, preflight_id: str, version: int) -> AgentTaskRecoveryPreflightDependencySnapshot:
        """task_id/preflight_id's exact snapshot, numbered `version`.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError:
                If task_id/preflight_id is not a non-empty string,
                version is not a positive int, no such version is
                recorded, or its own referenced snapshot no longer exists
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError("version must be a positive int")

        for entry in self.list_versions(task_id, preflight_id):
            if entry.version == version:
                snapshot = self._snapshot_service.get(task_id, entry.snapshot_id)
                if snapshot is None:
                    raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(
                        f"version {version} of task_id {task_id!r} / preflight_id {preflight_id!r} "
                        "references a snapshot that no longer exists"
                    )
                return snapshot

        raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(
            f"task_id {task_id!r} / preflight_id {preflight_id!r} has no version {version}"
        )

    def latest_version(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotVersion]:
        """task_id/preflight_id's highest-numbered version record, or
        None if none has ever been created."""
        versions = self.list_versions(task_id, preflight_id)
        return versions[-1] if versions else None

    def list_versions(self, task_id: str, preflight_id: str) -> list:
        """Every version ever recorded for (task_id, preflight_id),
        version 1 first."""
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._store.list_for_preflight(task_id, preflight_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError(
                f"{field_name} is required and must be a non-empty string"
            )
