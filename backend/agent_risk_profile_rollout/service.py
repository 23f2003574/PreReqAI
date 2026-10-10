from dataclasses import replace
from datetime import datetime, timezone

from backend.agent_risk_profile import ARCHIVED, LLMAgentRiskProfileService
from backend.agent_risk_profile_activation import (
    ArchivedRiskProfileCannotActivateError,
    IncompatibleRiskProfileVersionError,
    LLMAgentRiskProfileActivationService,
    RiskProfileScopeMismatchError,
)
from backend.agent_risk_profile_approval import APPROVED, LLMAgentRiskProfileApprovalService
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, profile_from_version

from .in_memory_store import InMemoryRiskProfileRolloutStore
from .models import (
    COMPLETED,
    FAILED,
    IN_PROGRESS,
    PAUSED,
    STANDARD,
    STANDARD_STAGES,
    STRATEGIES,
    RiskProfileRollout,
    new_rollout_id,
)
from .store import RiskProfileRolloutStore

_STAGES_BY_STRATEGY = {STANDARD: STANDARD_STAGES}


class UnknownRolloutError(KeyError):
    """Raised when get_rollout()/advance_rollout()/pause_rollout()/
    complete_rollout() is given a rollout_id that was never started."""


class InvalidRolloutStrategyError(ValueError):
    """Raised when start_rollout() is given a strategy that is not one
    of STRATEGIES."""


class RolloutRequiresApprovalError(ValueError):
    """Raised when start_rollout() is given a (profile_id, version,
    scope_id) that Commit #10's own approval service does not report as
    APPROVED (Rule: "Only an approved ... version may start rollout")."""


class ConflictingRolloutError(ValueError):
    """Raised when start_rollout() would create a second concurrently
    active (IN_PROGRESS or PAUSED) rollout for the same (profile_id,
    scope_id) pair (Rule: "Prevent conflicting concurrent rollouts for
    the same profile/scope")."""


class InvalidRolloutTransitionError(ValueError):
    """Raised when advance_rollout()/pause_rollout()/complete_rollout()
    is attempted against a rollout whose current state does not permit
    it (e.g. advancing a COMPLETED/FAILED rollout, or pausing one that
    is not IN_PROGRESS)."""


class IncompleteRolloutError(InvalidRolloutTransitionError):
    """Raised when complete_rollout() is called before every stage in
    the rollout's own strategy has succeeded (Rule: "Completion occurs
    only after every required stage succeeds")."""


class LLMAgentRiskProfileRolloutService:
    """Controlled, staged rollout of one Commit #10-approved risk
    profile version across its scope -- through the repository's real,
    existing activation mechanism, never a second deployment system.

    No multi-stage progressive rollout precedent exists anywhere in
    this repository (the closest infrastructure,
    backend.agent_policy_deployment_orchestration, is a single-shot
    deploy/verify/health/governance/rollback pipeline with no paused/
    resumed staged progression), so STANDARD is this commit's own
    minimal, deterministic staged strategy -- three safety checkpoints
    around the one real mutation a rollout ever performs, rather than
    an invented population/traffic-percentage rollout this series'
    scope model has no semantics for (Rule: "No runtime traffic
    shifting ... unless the repository already provides those
    capabilities" -- it does not):

        pre_flight  -- re-run Commit #3's validator and Commit #5's
                        compatibility check against the target version,
                        exactly as Commit #6's own activate() and
                        Commit #10's own request_approval() already do,
                        since time may have passed since approval
        activate    -- Commit #6's own
                        LLMAgentRiskProfileActivationService.activate(),
                        completely unmodified: the *only* mutation this
                        service ever performs, and the exact same
                        "compatibility gate runs before mutation, failed
                        activation leaves the previous version
                        unchanged" guarantee that class already provides
        verify      -- Commit #6's own get_active(scope_id), confirming
                        the live profile now genuinely reflects the
                        version this rollout is rolling out

    advance_rollout() moves through stages one at a time, in this exact
    order, and only ever appends the next stage once the current one has
    actually succeeded -- current_stage can therefore never "jump" past
    an unattempted one (Rule: "A rollout must never silently skip a
    stage"). A stage that fails transitions the rollout to FAILED
    (recording why in provenance) without current_stage ever advancing
    past the last one that *did* succeed -- since only "activate" can
    ever change the live profile, and Commit #6's own activate() already
    guarantees a failed attempt leaves the previously active version
    exactly as it was, "any failed stage preserves the previously active
    profile" holds structurally, not by a rollback step this service
    would otherwise have to perform itself.

    complete_rollout() is a distinct, explicit confirmation step -- it
    never happens automatically once the last stage succeeds -- and
    raises IncompleteRolloutError unless current_stage already names the
    strategy's own final stage (Rule: "Completion occurs only after
    every required stage succeeds").

    pause_rollout() only ever flips state to PAUSED; current_stage and
    stages are left completely untouched (Rule: "Pause must prevent
    further progression without losing rollout state"). There is no
    separate resume method: advance_rollout() on a PAUSED rollout first
    transitions it back to IN_PROGRESS and then proceeds with the next
    stage exactly as it otherwise would, so pausing never discards where
    a rollout had gotten to.

    "Record meaningful rollout state transitions using existing
    history/audit infrastructure" is satisfied by construction rather
    than by this service inventing its own recording call: the
    "activate" stage drives whatever activation_service a caller
    configured, unmodified -- when that happens to be Commit #7's own
    LLMAgentRiskProfileActivationHistoryTrackedService, an ACTIVATED
    history entry is recorded automatically, the same way it would be
    for any other caller of that class; this service holds no history
    reference of its own and never duplicates that recording.

    start_rollout() reuses Commit #10's own
    LLMAgentRiskProfileApprovalService.get_status() verbatim -- never a
    second approval check -- and Commit #3/#5's validator/compatibility
    directly, the same collaborators Commit #6/#10 already compose.
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        activation_service: LLMAgentRiskProfileActivationService,
        approval_service: LLMAgentRiskProfileApprovalService,
        compatibility: LLMAgentRiskProfileCompatibility = None,
        validator: LLMAgentRiskProfileValidator = None,
        store: RiskProfileRolloutStore = None,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._activation_service = activation_service
        self._approval_service = approval_service
        self._compatibility = compatibility if compatibility is not None else LLMAgentRiskProfileCompatibility()
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()
        self.store = store if store is not None else InMemoryRiskProfileRolloutStore()

    def start_rollout(self, profile_id: str, version: int, scope_id: str, strategy: str) -> RiskProfileRollout:
        """Start a new rollout of profile_id's version `version` for
        scope_id, using `strategy`.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
            ArchivedRiskProfileCannotActivateError: If profile_id is
                ARCHIVED
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record
            InvalidRolloutStrategyError: If strategy is not one of
                STRATEGIES
            RolloutRequiresApprovalError: If (profile_id, version,
                scope_id) is not currently APPROVED per Commit #10's own
                approval service
            IncompatibleRiskProfileVersionError: If the target version
                fails Commit #3's own validator or Commit #5's own
                compatibility check
            ConflictingRolloutError: If a rollout is already IN_PROGRESS
                or PAUSED for this exact (profile_id, scope_id)
        """
        if strategy not in STRATEGIES:
            raise InvalidRolloutStrategyError(f"strategy {strategy!r} is not one of {sorted(STRATEGIES)}")

        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )
        if profile.status == ARCHIVED:
            raise ArchivedRiskProfileCannotActivateError(f"profile {profile_id!r} is archived and cannot roll out")

        if self._approval_service.get_status(profile_id, version, scope_id) != APPROVED:
            raise RolloutRequiresApprovalError(
                f"profile {profile_id!r} version {version} is not approved for scope {scope_id!r}"
            )

        target_version = self._version_service.get_version(profile_id, version)
        self._check_pre_flight(profile, target_version, scope_id)

        conflicting = [
            rollout
            for rollout in self.store.list_for_profile_scope(profile_id, scope_id)
            if rollout.state in (IN_PROGRESS, PAUSED)
        ]
        if conflicting:
            raise ConflictingRolloutError(
                f"a rollout is already {conflicting[0].state} for profile {profile_id!r} in scope {scope_id!r}"
            )

        rollout = RiskProfileRollout(
            rollout_id=new_rollout_id(),
            profile_id=profile_id,
            version=version,
            scope_id=scope_id,
            strategy=strategy,
            state=IN_PROGRESS,
            current_stage=None,
            stages=_STAGES_BY_STRATEGY[strategy],
        )
        return self.store.save(rollout)

    def advance_rollout(self, rollout_id: str) -> RiskProfileRollout:
        """Attempt the next stage of rollout_id's own strategy.

        A PAUSED rollout is resumed (state -> IN_PROGRESS) and then
        advanced exactly as an already-IN_PROGRESS one would be.

        Raises:
            UnknownRolloutError: If rollout_id was never started
            InvalidRolloutTransitionError: If rollout_id is COMPLETED or
                FAILED, or every stage has already succeeded (call
                complete_rollout() instead)
        """
        rollout = self.get_rollout(rollout_id)
        if rollout.state in (COMPLETED, FAILED):
            raise InvalidRolloutTransitionError(
                f"rollout {rollout_id!r} is {rollout.state} and cannot be advanced further"
            )

        next_index = 0 if rollout.current_stage is None else rollout.stages.index(rollout.current_stage) + 1
        if next_index >= len(rollout.stages):
            raise InvalidRolloutTransitionError(
                f"rollout {rollout_id!r} has already succeeded every stage; call complete_rollout() instead"
            )
        stage = rollout.stages[next_index]

        try:
            stage_provenance = self._run_stage(stage, rollout)
        except Exception as error:
            failed = replace(
                rollout,
                state=FAILED,
                provenance={**rollout.provenance, "failed_stage": stage, "failure_reason": str(error)},
                updated_at=datetime.now(timezone.utc),
            )
            return self.store.save(failed)

        advanced = replace(
            rollout,
            state=IN_PROGRESS,
            current_stage=stage,
            provenance={**rollout.provenance, stage: stage_provenance},
            updated_at=datetime.now(timezone.utc),
        )
        return self.store.save(advanced)

    def pause_rollout(self, rollout_id: str) -> RiskProfileRollout:
        """Pause rollout_id. Idempotent if it is already PAUSED.

        Raises:
            UnknownRolloutError: If rollout_id was never started
            InvalidRolloutTransitionError: If rollout_id is COMPLETED or
                FAILED
        """
        rollout = self.get_rollout(rollout_id)
        if rollout.state == PAUSED:
            return rollout
        if rollout.state != IN_PROGRESS:
            raise InvalidRolloutTransitionError(f"rollout {rollout_id!r} is {rollout.state} and cannot be paused")

        paused = replace(rollout, state=PAUSED, updated_at=datetime.now(timezone.utc))
        return self.store.save(paused)

    def complete_rollout(self, rollout_id: str) -> RiskProfileRollout:
        """Mark rollout_id COMPLETED.

        Raises:
            UnknownRolloutError: If rollout_id was never started
            InvalidRolloutTransitionError: If rollout_id is PAUSED,
                FAILED, or already COMPLETED
            IncompleteRolloutError: If rollout_id's own current_stage is
                not yet the last stage in its strategy
        """
        rollout = self.get_rollout(rollout_id)
        if rollout.state != IN_PROGRESS:
            raise InvalidRolloutTransitionError(f"rollout {rollout_id!r} is {rollout.state} and cannot be completed")
        if rollout.current_stage != rollout.stages[-1]:
            raise IncompleteRolloutError(
                f"rollout {rollout_id!r} has not yet succeeded every stage "
                f"(currently at {rollout.current_stage!r} of {rollout.stages})"
            )

        now = datetime.now(timezone.utc)
        completed = replace(rollout, state=COMPLETED, completed_at=now, updated_at=now)
        return self.store.save(completed)

    def get_rollout(self, rollout_id: str) -> RiskProfileRollout:
        rollout = self.store.get(rollout_id)
        if rollout is None:
            raise UnknownRolloutError(rollout_id)
        return rollout

    def _run_stage(self, stage: str, rollout: RiskProfileRollout):
        profile = self._profile_service.get(rollout.profile_id)
        target_version = self._version_service.get_version(rollout.profile_id, rollout.version)

        if stage == "pre_flight":
            self._check_pre_flight(profile, target_version, rollout.scope_id)
            return {"revalidated": True}

        if stage == "activate":
            result = self._activation_service.activate(rollout.profile_id, rollout.version, rollout.scope_id)
            return result.to_dict()

        if stage == "verify":
            active = self._activation_service.get_active(rollout.scope_id)
            if active is None:
                raise InvalidRolloutTransitionError(
                    f"scope {rollout.scope_id!r} has no active scope-default profile after activation"
                )
            active_profile, active_version = active

            # The "activate" stage's own ActivationResult already names
            # exactly which live version number resulted from rolling out
            # rollout.version's own content -- restoring an older
            # version's content while a newer one is live mints a fresh
            # forward version number rather than reusing the requested
            # one (Commit #6's own, already-established guarantee), so
            # verify must confirm against that *resulting* number, never
            # the raw originally-requested rollout.version.
            expected_version = rollout.provenance.get("activate", {}).get("version", rollout.version)
            if active_profile.profile_id != rollout.profile_id or active_version.version != expected_version:
                raise InvalidRolloutTransitionError(
                    f"scope {rollout.scope_id!r} is active on profile {active_profile.profile_id!r} version "
                    f"{active_version.version}, not the rolled-out profile {rollout.profile_id!r} version "
                    f"{expected_version}"
                )
            return {"verified_profile_id": active_profile.profile_id, "verified_version": active_version.version}

        raise InvalidRolloutTransitionError(f"unknown stage {stage!r}")

    def _check_pre_flight(self, profile, target_version, scope_id) -> None:
        prospective = profile_from_version(profile, target_version)

        validation_result = self._validator.validate(prospective)
        if not validation_result.is_valid:
            raise IncompatibleRiskProfileVersionError(
                f"profile {profile.profile_id!r} version {target_version.version} is invalid and cannot roll "
                f"out: {[issue.to_dict() for issue in validation_result.issues]}"
            )

        compatibility_result = self._compatibility.check(prospective, {"scope_id": scope_id})
        if not compatibility_result.compatible:
            raise IncompatibleRiskProfileVersionError(
                f"profile {profile.profile_id!r} version {target_version.version} is not compatible with scope "
                f"{scope_id!r}: {'; '.join(compatibility_result.reasons)}"
            )
