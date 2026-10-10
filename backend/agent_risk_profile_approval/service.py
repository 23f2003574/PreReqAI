from dataclasses import replace
from datetime import datetime, timezone

from backend.agent_risk_profile import ARCHIVED, LLMAgentRiskProfileService
from backend.agent_risk_profile_activation import IncompatibleRiskProfileVersionError, RiskProfileScopeMismatchError
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_impact_analysis import LLMAgentRiskProfileImpactAnalyzer
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, profile_from_version

from .in_memory_store import InMemoryRiskProfileApprovalStore
from .models import APPROVED, NOT_REQUESTED, PENDING, REJECTED, RiskProfileApproval, new_approval_id
from .store import RiskProfileApprovalStore


class UnknownRiskProfileApprovalError(KeyError):
    """Raised when get()/approve()/reject() is given an approval_id that
    was never requested."""


class ArchivedRiskProfileCannotEnterApprovalError(ValueError):
    """Raised when request_approval() is given a profile_id that is
    ARCHIVED (Rule: "Archived versions cannot receive approval") -- an
    archived profile can never be activated at all (Commit #6's own
    ArchivedRiskProfileCannotActivateError), so approving a version for
    it would review a change that can never actually take effect."""


class InvalidApprovalTransitionError(ValueError):
    """Raised when approve()/reject() is given an approval_id that is
    no longer PENDING -- an approval is terminal once decided (Rule:
    "Preserve historical approval decisions; do not overwrite them"),
    the same "terminal once decided" discipline
    backend.agent_policy_risk_approval.ApprovalRequirement already
    established for an unrelated subject."""


class RejectionReasonRequiredError(InvalidApprovalTransitionError):
    """Raised when reject() is not given a reason (Rule: "Rejection
    requires a reason")."""


class UnauthorizedApproverError(ValueError):
    """Raised when approve()/reject() is given an actor a configured
    authorization callable rejects for this approval's own scope_id."""


class LLMAgentRiskProfileApprovalService:
    """An explicit human review gate for one Commit #1 risk profile's
    Commit #4 version, before it is ever handed to Commit #6's own
    activate() -- modeled on
    backend.agent_policy_risk_approval.ApprovalRequirement/
    LLMAgentRiskApprovalGate's own PENDING/APPROVED/REJECTED vocabulary
    and "terminal once decided, dataclasses.replace()-not-mutate"
    discipline, adapted here to a (profile_id, version, scope_id)
    subject instead of that gate's own (RiskDecision, action_context)
    one -- a from-scratch, same-shape reimplementation (this series' own
    established precedent) rather than a cross-domain import, since that
    gate's own ApprovalRequirement is permanently keyed to one specific
    action evaluation, an entirely different subject than "this profile
    version, for this scope".

    Not a parallel governance framework: request_approval() only ever
    *reads* through Commit #3's own LLMAgentRiskProfileValidator, Commit
    #5's own LLMAgentRiskProfileCompatibility, and (when configured)
    Commit #9's own LLMAgentRiskProfileImpactAnalyzer -- exactly the
    same gates Commit #6's own activate() already runs, run here
    read-only, before this service ever records anything (Rule: "Only
    valid, compatible versions can enter approval" / "reuse existing
    ... validation, compatibility, and impact-analysis infrastructure").
    approve()/reject() never call LLMAgentRiskProfileService or
    LLMAgentRiskProfileActivationService at all -- there is no
    profile/version mutation anywhere in this class, so "an approved
    version does not automatically activate" holds structurally, not by
    a documented promise (this series' architecture does not couple the
    two operations, so none is introduced here).

    Authorization is never invented here: approve()/reject() accept an
    optional `authorized: (actor, scope_id) -> bool` duck-typed
    callable, the exact same pattern
    backend.agent_policy_risk_review_assignment.LLMAgentRiskReviewAssignment
    already established for "who may review scope X" -- this service
    never decides who may approve/reject on its own authority, it only
    ever asks whatever the caller already has (Rule: "Do not duplicate
    authentication/authorization logic").
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        compatibility: LLMAgentRiskProfileCompatibility = None,
        validator: LLMAgentRiskProfileValidator = None,
        impact_analyzer: LLMAgentRiskProfileImpactAnalyzer = None,
        store: RiskProfileApprovalStore = None,
        authorized=None,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._compatibility = compatibility if compatibility is not None else LLMAgentRiskProfileCompatibility()
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()
        self._impact_analyzer = impact_analyzer
        self.store = store if store is not None else InMemoryRiskProfileApprovalStore()
        self._authorized = authorized

    def request_approval(self, profile_id: str, version: int, scope_id: str, requested_by: str) -> RiskProfileApproval:
        """Request approval for profile_id's version `version`, for
        scope_id.

        Idempotent for a still-PENDING request against the identical
        (profile_id, version, scope_id) key: the existing PENDING
        approval is returned as-is, never re-minted (Rule: "Prevent
        duplicate unresolved approval requests"). A key whose only prior
        request(s) already resolved (APPROVED/REJECTED) is free to
        receive a brand-new one -- those earlier records remain exactly
        as they were, retrievable forever (Rule: "Preserve historical
        approval decisions").

        Raises:
            UnknownRiskProfileError: If profile_id was never created
                (propagated unchanged from Commit #1's own get())
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
            ArchivedRiskProfileCannotEnterApprovalError: If profile_id
                is ARCHIVED
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record (propagated unchanged from Commit #4's
                own get_version())
            IncompatibleRiskProfileVersionError: If the requested
                version fails Commit #3's own validator or Commit #5's
                own compatibility check
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )
        if profile.status == ARCHIVED:
            raise ArchivedRiskProfileCannotEnterApprovalError(
                f"profile {profile_id!r} is archived and cannot enter approval"
            )

        target_version = self._version_service.get_version(profile_id, version)
        prospective = profile_from_version(profile, target_version)

        validation_result = self._validator.validate(prospective)
        if not validation_result.is_valid:
            raise IncompatibleRiskProfileVersionError(
                f"profile {profile_id!r} version {version} is invalid and cannot enter approval: "
                f"{[issue.to_dict() for issue in validation_result.issues]}"
            )

        compatibility_result = self._compatibility.check(prospective, {"scope_id": scope_id})
        if not compatibility_result.compatible:
            raise IncompatibleRiskProfileVersionError(
                f"profile {profile_id!r} version {version} is not compatible with scope {scope_id!r}: "
                f"{'; '.join(compatibility_result.reasons)}"
            )

        existing_pending = next(
            (approval for approval in self.store.list_for_key(profile_id, version, scope_id) if approval.status == PENDING),
            None,
        )
        if existing_pending is not None:
            return existing_pending

        impact_result = (
            self._impact_analyzer.analyze(profile_id, version, scope_id) if self._impact_analyzer is not None else None
        )

        approval = RiskProfileApproval(
            approval_id=new_approval_id(),
            profile_id=profile_id,
            version=version,
            scope_id=scope_id,
            status=PENDING,
            requested_by=requested_by,
            provenance={
                "validation": validation_result.to_dict(),
                "compatibility": compatibility_result.to_dict(),
                "impact_analysis": impact_result.to_dict() if impact_result is not None else None,
            },
        )
        return self.store.save(approval)

    def approve(self, approval_id: str, actor: str) -> RiskProfileApproval:
        """Approve approval_id.

        Raises:
            UnknownRiskProfileApprovalError: If approval_id was never
                requested
            InvalidApprovalTransitionError: If approval_id is no longer
                PENDING
            UnauthorizedApproverError: If a configured authorization
                callable rejects actor for this approval's scope_id
        """
        approval = self.get(approval_id)
        if approval.status != PENDING:
            raise InvalidApprovalTransitionError(
                f"approval {approval_id!r} is {approval.status}, not {PENDING}, and cannot be approved"
            )
        self._check_authorized(actor, approval.scope_id)

        resolved = replace(
            approval, status=APPROVED, approved_by=actor, resolved_at=datetime.now(timezone.utc)
        )
        return self.store.save(resolved)

    def reject(self, approval_id: str, actor: str, reason: str) -> RiskProfileApproval:
        """Reject approval_id.

        Raises:
            UnknownRiskProfileApprovalError: If approval_id was never
                requested
            InvalidApprovalTransitionError: If approval_id is no longer
                PENDING
            RejectionReasonRequiredError: If reason is missing or blank
            UnauthorizedApproverError: If a configured authorization
                callable rejects actor for this approval's scope_id
        """
        if not reason or not isinstance(reason, str):
            raise RejectionReasonRequiredError("reason is required to reject an approval")

        approval = self.get(approval_id)
        if approval.status != PENDING:
            raise InvalidApprovalTransitionError(
                f"approval {approval_id!r} is {approval.status}, not {PENDING}, and cannot be rejected"
            )
        self._check_authorized(actor, approval.scope_id)

        resolved = replace(
            approval, status=REJECTED, rejected_by=actor, reason=reason, resolved_at=datetime.now(timezone.utc)
        )
        return self.store.save(resolved)

    def get(self, approval_id: str) -> RiskProfileApproval:
        approval = self.store.get(approval_id)
        if approval is None:
            raise UnknownRiskProfileApprovalError(approval_id)
        return approval

    def get_status(self, profile_id: str, version: int, scope_id: str) -> str:
        """The current approval status for (profile_id, version,
        scope_id): PENDING or the most recently resolved APPROVED/
        REJECTED outcome, or NOT_REQUESTED when nothing has ever been
        requested for this exact key.

        A read-only lookup: never mutates anything, and repeated calls
        against unchanged history always return the same answer (Rule:
        "Approval state transitions are deterministic and auditable").
        """
        history = self.list_history(profile_id, version, scope_id)
        if not history:
            return NOT_REQUESTED

        pending = next((approval for approval in history if approval.status == PENDING), None)
        if pending is not None:
            return PENDING

        return history[-1].status

    def list_history(self, profile_id: str, version: int, scope_id: str) -> list:
        """Every approval ever requested for this exact (profile_id,
        version, scope_id) key, oldest first -- the complete history,
        never collapsed to just the latest (Rule: "Preserve historical
        approval decisions")."""
        return self.store.list_for_key(profile_id, version, scope_id)

    def _check_authorized(self, actor: str, scope_id: str) -> None:
        if self._authorized is not None and not self._authorized(actor, scope_id):
            raise UnauthorizedApproverError(f"{actor!r} is not authorized to decide approvals for scope {scope_id!r}")
