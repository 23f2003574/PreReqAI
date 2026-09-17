from datetime import datetime, timezone
from typing import Optional

from .models import (
    REPLACED,
    REUSED,
    REVALIDATION_FAILED,
    REVALIDATION_MISSING,
    AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult,
)
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService
from .trust import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError(ValueError):
    """Raised when revalidate() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService:
    """Rebuilds trust for a snapshot that has lost it, by creating a
    FRESH snapshot rather than ever reviving the old one -- never a
    second snapshot/versioning/integrity/signing/trust pipeline (Rule:
    "Reuse existing versioning, integrity, signing, and trust services
    ... do not duplicate any of those mechanisms"): every step below
    delegates to exactly one existing Commit #1-#6 service, in this
    fixed order:

      1. Commit #1's own get() loads the referenced snapshot.
      2. Commit #6's own validate() checks its CURRENT trust, fresh.
      3. If trusted (or, when a version_service is configured, if a
         LATER version for the same preflight_id already exists and is
         itself trusted -- Rule: "idempotent where an equivalent current
         trusted snapshot already exists"), that snapshot is returned
         unchanged as REUSED -- nothing new is created.
      4. Otherwise Commit #1's own create(task_id, preflight_id) resolves
         the CURRENT dependency graph into a brand-new snapshot, bound to
         the SAME preflight_id the old one had (Rule: "bound to the
         correct task/preflight").
      5. The new snapshot is versioned (Commit #3), integrity-verified
         (Commit #4), and signed (Commit #5) -- each only when its own
         optional collaborator was configured.
      6. Commit #6's own validate() checks the NEW snapshot's trust.
         REPLACED when trusted; REVALIDATION_FAILED when not -- reported
         honestly, never retried in a loop or silently treated as usable
         (Rule: "leave recovery non-actionable").

    Never modifies or revives the old snapshot (Rule): this class holds
    no reference to anything that could write to Commit #1's own store
    for an EXISTING snapshot_id -- create() always mints a fresh one.
    Preserves complete history (Rule): every write below is through an
    already-append-only service; nothing here ever deletes or rewrites a
    prior snapshot, version, integrity baseline, signature, or trust
    record. Never schedules/authorizes/executes recovery (Rule): no such
    collaborator is held.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        trust_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService = None,
        version_service=None,
        integrity_service=None,
        signing_service=None,
        audit_service=None,
    ):
        """
        Args:
            version_service: Optional Commit #3 version service (duck-
                typed). Enables versioning the new snapshot and the
                "already-revalidated" idempotency check via
                latest_version().
            integrity_service: Optional Commit #4 integrity service
                (duck-typed, only verify() is called) -- establishes the
                new snapshot's own trusted baseline.
            signing_service: Optional Commit #5 signing service (duck-
                typed, only sign() is called).
            audit_service: Optional Commit #11
                LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService
                (duck-typed, only record() is called). When given,
                revalidate() records its own already-computed result
                AFTER computing it -- purely an append, never influencing
                the result itself (Rule: "Integrate with #10 so every
                trust revalidation has traceable evidence").
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._trust_service = (
            trust_service if trust_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService()
        )
        self._version_service = version_service
        self._integrity_service = integrity_service
        self._signing_service = signing_service
        self._audit_service = audit_service

    def revalidate(
        self, task_id: str, snapshot_id: str
    ) -> AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult:
        """Rebuild trust for task_id's exact snapshot_id if it needs it.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        now = self._now()

        old_snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if old_snapshot is None:
            return self._result(task_id, None, snapshot_id, None, REVALIDATION_MISSING, None, None, now)

        preflight_id = old_snapshot.preflight_id
        old_trust = self._trust_service.validate(task_id, snapshot_id)

        reuse_snapshot_id, reuse_trust = self._already_trusted_current(task_id, snapshot_id, preflight_id, old_trust)
        if reuse_snapshot_id is not None:
            return self._result(
                task_id, preflight_id, snapshot_id, reuse_snapshot_id, REUSED, old_trust, reuse_trust, now
            )

        new_snapshot = self._snapshot_service.create(task_id, preflight_id)
        if self._version_service is not None:
            self._version_service.create_version(task_id, preflight_id, new_snapshot)
        if self._integrity_service is not None:
            self._integrity_service.verify(task_id, new_snapshot.snapshot_id)
        if self._signing_service is not None:
            self._signing_service.sign(task_id, new_snapshot.snapshot_id)

        new_trust = self._trust_service.validate(task_id, new_snapshot.snapshot_id)
        action = REPLACED if new_trust.trusted else REVALIDATION_FAILED

        return self._result(
            task_id, preflight_id, snapshot_id, new_snapshot.snapshot_id, action, old_trust, new_trust, now
        )

    def _result(self, task_id, preflight_id, old_snapshot_id, new_snapshot_id, action, old_trust, new_trust, now):
        result = AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult(
            task_id=task_id, preflight_id=preflight_id, old_snapshot_id=old_snapshot_id,
            new_snapshot_id=new_snapshot_id, action=action, old_trust=old_trust, new_trust=new_trust,
            revalidated_at=now,
        )
        if self._audit_service is not None:
            self._audit_service.record(task_id, old_snapshot_id, result)
        return result

    def _already_trusted_current(self, task_id: str, snapshot_id: str, preflight_id: str, old_trust) -> tuple:
        """(snapshot_id, trust_result) for a snapshot that is ALREADY
        trusted and usable for (task_id, preflight_id) -- the exact
        old_snapshot_id itself if old_trust is already trusted, else (when
        a version_service is configured) a LATER version a prior
        revalidate() call already produced and trusted (Rule: "idempotent
        where an equivalent current trusted snapshot already exists").
        (None, None) when nothing already-trusted exists, meaning a fresh
        snapshot must be built."""
        if old_trust.trusted:
            return snapshot_id, old_trust
        if self._version_service is not None and preflight_id:
            latest = self._version_service.latest_version(task_id, preflight_id)
            if latest is not None and latest.snapshot_id != snapshot_id:
                latest_trust = self._trust_service.validate(task_id, latest.snapshot_id)
                if latest_trust.trusted:
                    return latest.snapshot_id, latest_trust
        return None, None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
