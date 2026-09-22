from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationService

from .decision_freshness_policy import LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy
from .decision_integrity import LLMAgentTaskRecoveryExecutionDecisionIntegrityService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .drift import LLMAgentTaskRecoveryExecutionPreconditionDriftService
from .models import (
    FRESHNESS_UNKNOWN,
    INTEGRITY_VALID,
    AgentTaskRecoveryExecutionCurrentStateEvidence,
    AgentTaskRecoveryExecutionDecisionStalenessResult,
)
from .service import LLMAgentTaskRecoveryExecutionPreconditionSnapshotService

_AMBIGUOUS_MARKER = "cannot be safely compared"


class InvalidAgentTaskRecoveryExecutionDecisionStalenessError(ValueError):
    """Raised when check() is given invalid arguments, or decision_id
    names no decision recorded for task_id."""


class LLMAgentTaskRecoveryExecutionDecisionStalenessService:
    """Detects whether a Commit #7-persisted decision is too old to
    safely represent current recovery state -- never a new lifecycle/TTL
    policy (Rule: "Do not invent a new lifecycle policy"): check() only
    ever reads through Commit #1's own integrity check, Commit #1's own
    latest_for_authorization(), and Commit #3's own classify() -- it
    never recomputes or alters the decision itself.

    Prefers explicit version changes over TTLs (Rule): staleness is
    decided from two identity/evidence signals, never elapsed time --
    (1) whether a NEWER snapshot has since been captured for the
    decision's own authorization_id (Commit #1's own
    latest_for_authorization(), the same explicit "a new baseline exists"
    signal Commit #4's own revalidate() already relies on), and (2)
    Commit #3's own drift classification of the decision's own
    snapshot_id.

    Reuses Commit #1's integrity check before trusting anything (Rule):
    a decision that fails integrity is reported UNKNOWN immediately --
    every other check is skipped since there is nothing trustworthy left
    to compare against.

    Never declares FRESH on incomplete evidence (Rule): any drift item
    whose own reason says a field "cannot be safely compared" (Commit
    #3's own ambiguous-collaborator-missing wording) forces UNKNOWN, even
    if every other signal looks clean.

    Delegates the actual fresh/stale/indeterminate verdict to Commit #3's
    own LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy (Rule:
    "Integrate it into the staleness service from #2"): check() only ever
    gathers the evidence (integrity, latest snapshot version, drift), then
    calls the policy's own explain() -- the comparison logic itself lives
    in exactly one place, never duplicated here.

    Read-only (Rule): every call here only ever reads.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        drift_service: LLMAgentTaskRecoveryExecutionPreconditionDriftService = None,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        integrity_service: LLMAgentTaskRecoveryExecutionDecisionIntegrityService = None,
        policy: LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy = None,
    ):
        """
        Args:
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore.
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshots capture()
                actually produced, so latest_for_authorization() reflects
                real history.
            drift_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDriftService;
                pass the real instance wired to live guard/authorization/
                readiness/retry-eligibility collaborators.
            integrity_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionDecisionIntegrityService,
                built from the same decision_store/snapshot_service given
                here.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._drift_service = (
            drift_service if drift_service is not None else LLMAgentTaskRecoveryExecutionPreconditionDriftService()
        )
        self._integrity_service = (
            integrity_service
            if integrity_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionIntegrityService(
                decision_store=self._decision_store, snapshot_service=self._snapshot_service,
                authorization_service=authorization_service,
            )
        )
        self._policy = policy if policy is not None else LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()

    def check(self, task_id: str, decision_id: str) -> AgentTaskRecoveryExecutionDecisionStalenessResult:
        """Check whether task_id's exact decision_id is still fresh.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionStalenessError: If
                task_id/decision_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")

        integrity = self._integrity_service.check(task_id, decision_id)
        decision = self._decision_store.get(decision_id)
        if integrity.status != INTEGRITY_VALID or decision is None:
            return AgentTaskRecoveryExecutionDecisionStalenessResult(
                task_id=task_id, decision_id=decision_id, status=FRESHNESS_UNKNOWN,
                reason=f"decision integrity check failed: {'; '.join(integrity.issues) or 'decision not found'}",
                decision_timestamp=decision.created_at if decision is not None else None,
                current_state_version=None,
                decision_state_version=decision.snapshot_id if decision is not None else None,
                checked_at=self._now(),
            )

        current_state_version = None
        if decision.authorization_id is not None:
            latest = self._snapshot_service.latest_for_authorization(task_id, decision.authorization_id)
            if latest is not None:
                current_state_version = latest.snapshot_id

        try:
            drift = self._drift_service.classify(task_id, decision.snapshot_id)
        except Exception as error:
            return AgentTaskRecoveryExecutionDecisionStalenessResult(
                task_id=task_id, decision_id=decision_id, status=FRESHNESS_UNKNOWN,
                reason=f"drift classification could not be computed: {error}",
                decision_timestamp=decision.created_at,
                current_state_version=current_state_version, decision_state_version=decision.snapshot_id,
                checked_at=self._now(),
            )

        ambiguous = any(_AMBIGUOUS_MARKER in item.reason for item in drift.items)
        evidence = AgentTaskRecoveryExecutionCurrentStateEvidence(
            current_state_version=current_state_version, drift_category=drift.category, ambiguous=ambiguous
        )
        return self._policy.explain(decision, evidence)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionStalenessError(
                f"{field_name} is required and must be a non-empty string"
            )
