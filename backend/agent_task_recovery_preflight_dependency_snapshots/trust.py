from datetime import datetime, timezone

from .integrity import LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService
from .models import INVALID, MISSING, UNVERIFIABLE, AgentTaskRecoveryPreflightDependencySnapshotTrustResult
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError(ValueError):
    """Raised when validate()/is_trusted() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService:
    """The single boundary recovery-preflight reconciliation must pass a
    snapshot through before using it -- never a second crypto/integrity/
    dependency-resolution implementation (Rule: "Do not duplicate
    hashing, signing, or dependency-resolution logic"): validate() only
    ever composes Commit #1's own get()/diff(), Commit #3's own
    latest_version(), Commit #4's own verify(), and (when configured)
    Commit #5's own verify_signature() -- nothing here recomputes a hash,
    an HMAC, or a dependency-graph traversal itself.

    Six checks, all collected (Rule: "Fail closed ... collect every
    blocking reason"):
      1. existence/ownership -- Commit #1's own get(task_id, snapshot_id)
         already returns None for a wrong task_id or unknown snapshot_id
         (the same "wrong task_id makes it invisible" convention this
         whole package uses); nothing further is checked when this fails.
      2/3. version consistency + integrity -- Commit #4's own verify()
         already flags an ambiguous multi-version binding as CORRUPTED
         (see integrity.py's own docstring), so a single verify() call
         covers both.
      4. signature, only when a signing_service is configured: INVALID
         or UNVERIFIABLE always blocks; MISSING blocks only when
         require_signature=True (Rule: "signature verification succeeds
         WHERE SIGNING IS REQUIRED" -- not configuring signing at all, or
         configuring it without requiring it, is a legitimate posture).
      5. supersession, only when a version_service is configured: a
         snapshot that is no longer task_id/preflight_id's own latest
         version is treated as superseded by existing repository state.
         (No revocation mechanism exists anywhere in this series yet --
         only supersession is checked.)
      6. usability for reconciliation -- a real Commit #1 diff() call;
         any exception it raises blocks trust.

    Read-only (Rule): every one of the above is a read through an
    existing service; this class writes nothing of its own, ever.

    Deterministic/idempotent (Rule): a pure composition of already-
    deterministic reads (Commit #4/#5's own trust-on-first-use baselines
    notwithstanding -- once established, both are themselves stable), so
    two validate() calls against unchanged state always agree.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        integrity_service: LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService = None,
        signing_service=None,
        version_service=None,
        require_signature: bool = False,
    ):
        """
        Args:
            signing_service: Optional Commit #5
                LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService
                (duck-typed, only verify_signature() is called).
            version_service: Optional Commit #3
                LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService
                (duck-typed, only latest_version() is called) -- enables
                the supersession check.
            require_signature: When True and signing_service is given, a
                MISSING signature blocks trust; when False (default), a
                missing signature is merely reported, never blocking.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._integrity_service = (
            integrity_service
            if integrity_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(snapshot_service=self._snapshot_service)
        )
        self._signing_service = signing_service
        self._version_service = version_service
        self._require_signature = require_signature

    def is_trusted(self, task_id: str, snapshot_id: str) -> bool:
        """Shorthand for validate(task_id, snapshot_id).trusted."""
        return self.validate(task_id, snapshot_id).trusted

    def validate(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotTrustResult:
        """The single trust verdict for task_id's exact snapshot_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            return self._result(
                task_id, snapshot_id, None, None, None, None,
                ("no snapshot is recorded for this task_id/snapshot_id (or it belongs to a different task)",),
            )

        reasons = []

        integrity_status = None
        integrity_version = None
        try:
            integrity_result = self._integrity_service.verify(task_id, snapshot_id)
            integrity_status = integrity_result.status
            integrity_version = integrity_result.version
            if not integrity_result.valid:
                reasons.append(
                    f"integrity verification failed ({integrity_result.status}): "
                    f"{'; '.join(integrity_result.reasons) or 'no reason given'}"
                )
        except Exception as error:
            reasons.append(f"integrity verification is unavailable: {error}")

        signature_status = None
        if self._signing_service is not None:
            try:
                signature_result = self._signing_service.verify_signature(task_id, snapshot_id)
                signature_status = signature_result.status
                if signature_result.status in (INVALID, UNVERIFIABLE):
                    reasons.append(
                        f"signature verification failed ({signature_result.status}): "
                        f"{'; '.join(signature_result.reasons) or 'no reason given'}"
                    )
                elif signature_result.status == MISSING and self._require_signature:
                    reasons.append("signature is required but none is recorded for this snapshot")
            except Exception as error:
                reasons.append(f"signature verification is unavailable: {error}")

        if self._version_service is not None:
            latest = self._version_service.latest_version(snapshot.task_id, snapshot.preflight_id)
            if latest is not None and latest.snapshot_id != snapshot_id:
                reasons.append(f"snapshot has been superseded by version {latest.version}")

        try:
            self._snapshot_service.diff(task_id, snapshot_id)
        except Exception as error:
            reasons.append(f"dependency data is not usable for reconciliation: {error}")

        return self._result(
            task_id, snapshot_id, snapshot.preflight_id, integrity_version,
            integrity_status, signature_status, tuple(reasons),
        )

    def _result(self, task_id, snapshot_id, preflight_id, version, integrity_status, signature_status, reasons):
        return AgentTaskRecoveryPreflightDependencySnapshotTrustResult(
            task_id=task_id, snapshot_id=snapshot_id, preflight_id=preflight_id, version=version,
            trusted=not reasons, integrity_status=integrity_status, signature_status=signature_status,
            blocking_reasons=reasons, validated_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError(
                f"{field_name} is required and must be a non-empty string"
            )
