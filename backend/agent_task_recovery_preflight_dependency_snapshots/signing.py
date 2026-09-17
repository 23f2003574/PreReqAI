import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.storage import AtomicJsonFile

from .integrity import LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService
from .models import (
    INVALID,
    MISSING,
    UNVERIFIABLE,
    VALID,
    AgentTaskRecoveryPreflightDependencySnapshotSignature,
    AgentTaskRecoveryPreflightDependencySnapshotSignatureVerification,
)
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService

# Rule: "Do not introduce a standalone key-management service" -- this is
# a plain, documented default for development/testing only. A real
# deployment passes its own signing_key explicitly; this class never
# manages, rotates, or stores keys itself.
_DEFAULT_SIGNING_KEY = "agent-task-recovery-preflight-dependency-snapshot-signing-dev-key"


class InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError(ValueError):
    """Raised when sign()/verify_signature() is given invalid arguments,
    or sign() is asked for a snapshot that does not exist."""


class AgentTaskRecoveryPreflightDependencySnapshotSignatureStore(ABC):
    """Raw, append-only persistence for
    AgentTaskRecoveryPreflightDependencySnapshotSignature records, indexed
    by (task_id, snapshot_id). No update()/delete(): a signature, once
    recorded, is never rewritten (Rule: "don't overwrite prior
    signatures")."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryPreflightDependencySnapshotSignature
    ) -> AgentTaskRecoveryPreflightDependencySnapshotSignature:
        ...

    @abstractmethod
    def list_for_snapshot(self, task_id: str, snapshot_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryPreflightDependencySnapshotSignatureStore(AgentTaskRecoveryPreflightDependencySnapshotSignatureStore):
    """Stores signature records in memory, for development and testing."""

    def __init__(self):
        self._by_snapshot: dict = {}

    def save(self, record):
        stored = deepcopy(record)
        self._by_snapshot.setdefault((record.task_id, record.snapshot_id), []).append(stored)
        return deepcopy(stored)

    def list_for_snapshot(self, task_id, snapshot_id):
        entries = self._by_snapshot.get((task_id, snapshot_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.signed_at)]


class JsonAgentTaskRecoveryPreflightDependencySnapshotSignatureStore(AgentTaskRecoveryPreflightDependencySnapshotSignatureStore):
    """Persists signature records to a JSON file, keyed by
    "task_id::snapshot_id"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, snapshot_id: str) -> str:
        return f"{task_id}::{snapshot_id}"

    def save(self, record):
        records = self.file.read()
        key = self._key(record.task_id, record.snapshot_id)
        records.setdefault(key, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_snapshot(self, task_id, snapshot_id):
        entries = self.file.read().get(self._key(task_id, snapshot_id), [])
        matching = [AgentTaskRecoveryPreflightDependencySnapshotSignature.from_dict(data) for data in entries]
        return sorted(matching, key=lambda item: item.signed_at)


class LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService:
    """Adds authenticity metadata to a Commit #1 snapshot, so a consumer
    can tell a repository-produced snapshot apart from an untrusted one
    -- never a second crypto/key-management framework (Rule: "Reuse
    existing repository crypto/key abstractions where available"; "Do
    not introduce a standalone key-management service"): no HMAC/key
    abstraction was found anywhere else in this repository (checked
    first), so this class uses Python's own stdlib hmac+hashlib directly,
    the smallest possible addition, with a single plain `signing_key`
    constructor argument -- never a key store, rotation policy, or
    external KMS integration of its own.

    Signs Commit #4's own canonical representation (Rule: "Sign the
    canonical snapshot representation used by the integrity service"):
    the signed payload is {task_id, preflight_id, snapshot_id, version,
    integrity_value}, where integrity_value is
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService.
    compute()'s own output -- never a second, independently-derived
    canonicalization of the snapshot's dependency content.

    verify_signature() checks BOTH authenticity and integrity before
    calling anything VALID (Rule): it always calls Commit #4's own
    verify() first (not compute() -- verify() is what actually detects
    tampering against a baseline) and folds a non-VALID integrity
    verdict into its own INVALID/MISSING/UNVERIFIABLE result, in
    addition to independently recomputing and comparing the HMAC itself
    and cross-checking the stored signature's own bound identity
    (task_id/preflight_id/snapshot_id/version) against the snapshot's
    CURRENT identity.

    Preserves signature history (Rule): sign() always appends a new,
    immutable record via the store's own append-only save() -- it never
    checks for or reuses an existing signature the way #1-#4's own
    content-addressed writes do, so repeated signing is always possible
    and nothing already recorded is ever overwritten.

    Never modifies recovery/scheduling state or executes anything
    (Rule): this class holds no reference to anything that could.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        integrity_service: LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService = None,
        version_service=None,
        store: AgentTaskRecoveryPreflightDependencySnapshotSignatureStore = None,
        signing_key: str = None,
    ):
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._integrity_service = (
            integrity_service
            if integrity_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(snapshot_service=self._snapshot_service)
        )
        self._version_service = version_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightDependencySnapshotSignatureStore()
        self._signing_key = signing_key if signing_key is not None else _DEFAULT_SIGNING_KEY

    def sign(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotSignature:
        """Sign task_id's exact, current snapshot_id. Always appends a
        new signature record, even if one already exists.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError:
                If task_id/snapshot_id is not a non-empty string, or no
                such snapshot is recorded for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        integrity_value = self._integrity_service.compute(task_id, snapshot_id)
        version = self._resolve_version(snapshot)
        signature = self._sign_value(task_id, snapshot.preflight_id, snapshot_id, version, integrity_value)

        record = AgentTaskRecoveryPreflightDependencySnapshotSignature(
            task_id=task_id, preflight_id=snapshot.preflight_id, snapshot_id=snapshot_id, version=version,
            integrity_value=integrity_value, signature=signature, signed_at=self._now(),
        )
        return self._store.save(record)

    def verify_signature(
        self, task_id: str, snapshot_id: str
    ) -> AgentTaskRecoveryPreflightDependencySnapshotSignatureVerification:
        """Verify task_id's exact snapshot_id against its own MOST
        RECENT signature. Read-only: never mutates the snapshot, the
        signature history, or any other state.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        records = self._store.list_for_snapshot(task_id, snapshot_id)
        if not records:
            return self._result(task_id, snapshot_id, None, None, MISSING, None, None,
                                 ("no signature is recorded for this task_id/snapshot_id",))
        latest = records[-1]

        integrity_result = self._integrity_service.verify(task_id, snapshot_id)
        if integrity_result.status == MISSING:
            return self._result(task_id, snapshot_id, latest.preflight_id, latest.version, MISSING,
                                 latest.signature_id, integrity_result.status, ("snapshot no longer exists",))

        try:
            snapshot = self._snapshot_service.get(task_id, snapshot_id)
            version = self._resolve_version(snapshot)
            reasons = []

            if not integrity_result.valid:
                reasons.append(
                    f"snapshot integrity check failed ({integrity_result.status}): "
                    f"{'; '.join(integrity_result.reasons) or 'no reason given'}"
                )

            if (latest.task_id, latest.preflight_id, latest.snapshot_id, latest.version) != (
                task_id, snapshot.preflight_id, snapshot_id, version,
            ):
                reasons.append("signature was recorded for a different task/preflight/snapshot/version identity")
            else:
                expected = self._sign_value(task_id, snapshot.preflight_id, snapshot_id, version, integrity_result.integrity_value)
                if latest.signature != expected:
                    reasons.append("signature does not authenticate the current snapshot content")

            status = INVALID if reasons else VALID
            return self._result(task_id, snapshot_id, snapshot.preflight_id, version, status,
                                 latest.signature_id, integrity_result.status, tuple(reasons))
        except Exception as error:
            return self._result(task_id, snapshot_id, latest.preflight_id, latest.version, UNVERIFIABLE,
                                 latest.signature_id, None, (f"signature could not be verified: {error}",))

    def list_signatures(self, task_id: str, snapshot_id: str) -> list:
        """Every signature ever recorded for (task_id, snapshot_id),
        oldest first -- the complete, never-overwritten history."""
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        return self._store.list_for_snapshot(task_id, snapshot_id)

    def _resolve_version(self, snapshot) -> Optional[int]:
        if self._version_service is None:
            return None
        matches = [
            entry.version
            for entry in self._version_service.list_versions(snapshot.task_id, snapshot.preflight_id)
            if entry.snapshot_id == snapshot.snapshot_id
        ]
        return matches[-1] if matches else None

    def _sign_value(self, task_id, preflight_id, snapshot_id, version, integrity_value) -> str:
        payload = json.dumps(
            {"task_id": task_id, "preflight_id": preflight_id, "snapshot_id": snapshot_id,
             "version": version, "integrity_value": integrity_value},
            sort_keys=True, default=str,
        )
        digest = hmac.new(self._signing_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"hmac-sha256:{digest}"

    def _result(self, task_id, snapshot_id, preflight_id, version, status, signature_id, integrity_status, reasons):
        return AgentTaskRecoveryPreflightDependencySnapshotSignatureVerification(
            task_id=task_id, snapshot_id=snapshot_id, preflight_id=preflight_id, version=version,
            status=status, valid=status == VALID, signature_id=signature_id, integrity_status=integrity_status,
            reasons=reasons, verified_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError(
                f"{field_name} is required and must be a non-empty string"
            )
