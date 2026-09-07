from backend.agent_risk_profile import LLMAgentRiskProfileService
from backend.agent_risk_profile_activation import RiskProfileScopeMismatchError
from backend.agent_risk_profile_approval import APPROVED, LLMAgentRiskProfileApprovalService
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_drift_detection import LLMAgentRiskProfileDriftDetector
from backend.agent_risk_profile_impact_analysis import LLMAgentRiskProfileImpactAnalyzer
from backend.agent_risk_profile_rollout import FAILED as ROLLOUT_FAILED_STATE
from backend.agent_risk_profile_rollout import STANDARD, LLMAgentRiskProfileRolloutService
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, profile_from_version

from .models import (
    BLOCKED,
    DRIFTED,
    NOT_APPROVED,
    PENDING_APPROVAL,
    ROLLED_OUT,
    ROLLOUT_FAILED,
    STABLE,
    RiskProfileGovernanceResult,
)

DEFAULT_REQUESTED_BY = "risk-profile-governance-orchestrator"


class LLMAgentRiskProfileGovernanceOrchestrator:
    """The final composition root for this entire Agent Risk Profile
    subsystem: coordinates Commits #1-#12's own already-shipped services
    through the complete prepare -> approve -> roll out -> assess
    lifecycle, without reimplementing a single one of them.

    Every actual decision is delegated to a real collaborator this
    subsystem already ships -- Commit #3's own LLMAgentRiskProfileValidator,
    Commit #5's own LLMAgentRiskProfileCompatibility, Commit #9's own
    LLMAgentRiskProfileImpactAnalyzer, Commit #10's own
    LLMAgentRiskProfileApprovalService, Commit #11's own
    LLMAgentRiskProfileRolloutService, and Commit #12's own
    LLMAgentRiskProfileDriftDetector -- each called exactly the way its
    own commit already established, never a second time with different
    (looser) rules. This class's only real work is sequencing those
    calls and reshaping their already-real results into one
    RiskProfileGovernanceResult per entry point; there is no rule-
    matching, scoring, compatibility, or state-transition logic
    anywhere in this file that any of those six collaborators does not
    already own.

    "A failed prerequisite stops dependent operations" holds by
    construction in prepare(): validation is checked, and only if it
    passes is compatibility checked; only if that passes is impact
    analysis run; only if that finds no blocking_conflicts is Commit
    #10's own request_approval() ever called. None of these are
    exceptions to catch -- LLMAgentRiskProfileValidator.validate()/
    LLMAgentRiskProfileCompatibility.check() never raise for an
    invalid/incompatible input, they report it as data (is_valid/
    compatible), so there is nothing to swallow at any of these steps;
    genuine exceptions (UnknownRiskProfileError, RiskProfileScopeMismatchError,
    UnknownRiskProfileVersionError, ConflictingRolloutError, ...) are
    never caught here and always propagate unchanged (Rule: "Do not
    swallow errors from underlying services").

    "Never silently activate or deploy an unapproved/incompatible
    version" holds the same way in approve_and_rollout(): an approval
    that is not APPROVED never reaches Commit #11's own start_rollout()
    at all -- it is reported as NOT_APPROVED instead. Commit #11's own
    rollout stages independently re-verify validation/compatibility a
    second time (its own "pre_flight" stage) before ever touching
    Commit #6's real activate() -- this orchestrator does not duplicate
    that re-check, it simply drives Commit #11's own advance_rollout()/
    complete_rollout() through to a real, observable outcome.

    "Use existing provenance/history/audit mechanisms rather than
    creating another audit trail" holds because this class holds no
    history/audit *store* reference of its own at all -- whatever
    history gets recorded is exactly whatever the activation_service a
    caller wired into the rollout_service already records (Commit #7),
    completely unaffected by this orchestrator's own existence.

    No background workers, queues, or schedulers: every method here
    runs its entire sequence synchronously, to completion, within one
    call -- the same "no invented runtime infrastructure" discipline
    every commit in this series has kept since Commit #1.
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        approval_service: LLMAgentRiskProfileApprovalService,
        rollout_service: LLMAgentRiskProfileRolloutService,
        drift_detector: LLMAgentRiskProfileDriftDetector,
        impact_analyzer: LLMAgentRiskProfileImpactAnalyzer = None,
        validator: LLMAgentRiskProfileValidator = None,
        compatibility: LLMAgentRiskProfileCompatibility = None,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._approval_service = approval_service
        self._rollout_service = rollout_service
        self._drift_detector = drift_detector
        self._impact_analyzer = (
            impact_analyzer
            if impact_analyzer is not None
            else LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service)
        )
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()
        self._compatibility = compatibility if compatibility is not None else LLMAgentRiskProfileCompatibility()

    def prepare(
        self, profile_id: str, version: int, scope_id: str, requested_by: str = DEFAULT_REQUESTED_BY
    ) -> RiskProfileGovernanceResult:
        """Coordinate validation -> compatibility -> impact analysis ->
        approval readiness for profile_id's version `version` in
        scope_id, requesting approval (Commit #10) once every earlier
        stage has passed.

        Stops, and reports BLOCKED with the concrete reasons, at
        whichever stage first finds a problem -- later stages are never
        run, and Commit #10's own request_approval() is never called
        (Rule: "never silently activate or deploy an unapproved/
        incompatible version" -- there is nothing to even request
        approval for until every earlier gate has genuinely passed).

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )

        target_version = self._version_service.get_version(profile_id, version)
        prospective = profile_from_version(profile, target_version)

        validation_result = self._validator.validate(prospective)
        if not validation_result.is_valid:
            reasons = [f"{issue.code}: {issue.message}" for issue in validation_result.issues]
            return self._result(
                profile_id, version, scope_id, governance_state=BLOCKED, blocking_reasons=reasons,
                validation_result=validation_result,
            )

        compatibility_result = self._compatibility.check(prospective, {"scope_id": scope_id})
        if not compatibility_result.compatible:
            return self._result(
                profile_id, version, scope_id, governance_state=BLOCKED,
                blocking_reasons=list(compatibility_result.reasons),
                validation_result=validation_result, compatibility_result=compatibility_result,
            )

        impact_result = self._impact_analyzer.analyze(profile_id, version, scope_id)
        if impact_result.blocking_conflicts:
            return self._result(
                profile_id, version, scope_id, governance_state=BLOCKED,
                blocking_reasons=list(impact_result.blocking_conflicts),
                warnings=[str(warning) for warning in impact_result.warnings],
                validation_result=validation_result, compatibility_result=compatibility_result,
                impact_result=impact_result,
            )

        approval = self._approval_service.request_approval(profile_id, version, scope_id, requested_by=requested_by)

        return self._result(
            profile_id, version, scope_id, governance_state=PENDING_APPROVAL,
            warnings=[str(warning) for warning in impact_result.warnings],
            validation_result=validation_result, compatibility_result=compatibility_result,
            impact_result=impact_result, approval_status=approval.status,
        )

    def approve_and_rollout(self, approval_id: str) -> RiskProfileGovernanceResult:
        """Verify approval_id is APPROVED and, only then, delegate the
        entire rollout to Commit #11's own
        LLMAgentRiskProfileRolloutService -- driven synchronously
        through every stage to either COMPLETED or FAILED within this
        one call (Rule: "no background workers, queues, or schedulers").

        Raises:
            UnknownRiskProfileApprovalError: If approval_id was never
                requested (propagated unchanged from Commit #10's own
                get())
            UnknownRiskProfileError, ArchivedRiskProfileCannotActivateError,
            UnknownRiskProfileVersionError, IncompatibleRiskProfileVersionError,
            ConflictingRolloutError: Propagated unchanged from Commit
                #11's own start_rollout(), when approval_id is APPROVED
        """
        approval = self._approval_service.get(approval_id)

        if approval.status != APPROVED:
            return self._result(
                approval.profile_id, approval.version, approval.scope_id, governance_state=NOT_APPROVED,
                blocking_reasons=[f"approval {approval_id!r} is {approval.status}, not {APPROVED}"],
                approval_status=approval.status,
            )

        rollout = self._rollout_service.start_rollout(
            approval.profile_id, approval.version, approval.scope_id, STANDARD
        )
        for _ in rollout.stages:
            rollout = self._rollout_service.advance_rollout(rollout.rollout_id)
            if rollout.state == ROLLOUT_FAILED_STATE:
                break

        if rollout.state == ROLLOUT_FAILED_STATE:
            blocking_reasons = [
                f"rollout {rollout.rollout_id!r} failed at stage {rollout.provenance.get('failed_stage')!r}: "
                f"{rollout.provenance.get('failure_reason')}"
            ]
            governance_state = ROLLOUT_FAILED
        else:
            rollout = self._rollout_service.complete_rollout(rollout.rollout_id)
            blocking_reasons = []
            governance_state = ROLLED_OUT

        return self._result(
            approval.profile_id, approval.version, approval.scope_id, governance_state=governance_state,
            blocking_reasons=blocking_reasons, approval_status=approval.status, rollout_status=rollout.state,
        )

    def assess_active(self, profile_id: str, scope_id: str) -> RiskProfileGovernanceResult:
        """Evaluate profile_id's own currently live state for scope_id
        using Commit #5's own compatibility check (against the live
        profile directly) and Commit #12's own drift detector (which
        itself already composes Commit #8/#9's simulation/impact
        logic) -- never a third, independent risk evaluation.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )

        compatibility_result = self._compatibility.check(profile, {"scope_id": scope_id})
        drift_result = self._drift_detector.detect(profile_id, scope_id)
        approval_status = self._approval_service.get_status(profile_id, profile.version, scope_id)

        recorded_rollouts = self._rollout_service.store.list_for_profile_scope(profile_id, scope_id)
        rollout_status = recorded_rollouts[-1].state if recorded_rollouts else None

        if not compatibility_result.compatible:
            governance_state = BLOCKED
            blocking_reasons = list(compatibility_result.reasons)
        elif drift_result.drift_detected:
            governance_state = DRIFTED
            blocking_reasons = []
        else:
            governance_state = STABLE
            blocking_reasons = []

        return self._result(
            profile_id, profile.version, scope_id, governance_state=governance_state,
            blocking_reasons=blocking_reasons, warnings=list(drift_result.details),
            compatibility_result=compatibility_result, drift_result=drift_result,
            approval_status=approval_status, rollout_status=rollout_status,
        )

    @staticmethod
    def _result(
        profile_id,
        version,
        scope_id,
        governance_state,
        blocking_reasons=None,
        warnings=None,
        validation_result=None,
        compatibility_result=None,
        impact_result=None,
        drift_result=None,
        approval_status=None,
        rollout_status=None,
    ) -> RiskProfileGovernanceResult:
        return RiskProfileGovernanceResult(
            profile_id=profile_id,
            version=version,
            scope_id=scope_id,
            validation_result=validation_result,
            compatibility_result=compatibility_result,
            impact_result=impact_result,
            approval_status=approval_status,
            rollout_status=rollout_status,
            drift_result=drift_result,
            governance_state=governance_state,
            blocking_reasons=blocking_reasons or [],
            warnings=warnings or [],
        )
