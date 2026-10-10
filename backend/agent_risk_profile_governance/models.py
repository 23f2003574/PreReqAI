from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# The orchestrator's own rollup of "where the lifecycle currently
# stands" -- deliberately a small, closed vocabulary derived entirely
# from the real sub-results this class already holds (never a second
# source of truth): BLOCKED/NOT_APPROVED/ROLLOUT_FAILED are the three
# distinct ways a stage can refuse to proceed (validation, compatibility,
# or impact-analysis blockers; an approval that is not yet APPROVED; a
# rollout stage that failed), PENDING_APPROVAL/ROLLED_OUT are the two
# forward-progress outcomes, and STABLE/DRIFTED are assess_active()'s
# own two possible verdicts on an already-active profile.
BLOCKED = "blocked"
PENDING_APPROVAL = "pending_approval"
NOT_APPROVED = "not_approved"
ROLLED_OUT = "rolled_out"
ROLLOUT_FAILED = "rollout_failed"
STABLE = "stable"
DRIFTED = "drifted"
GOVERNANCE_STATES = frozenset(
    {BLOCKED, PENDING_APPROVAL, NOT_APPROVED, ROLLED_OUT, ROLLOUT_FAILED, STABLE, DRIFTED}
)


@dataclass(frozen=True)
class RiskProfileGovernanceResult:
    """The orchestrator's complete, structured account of where one
    (profile_id, version, scope_id) lifecycle currently stands, for
    whichever of prepare()/approve_and_rollout()/assess_active()
    produced it.

    validation_result/compatibility_result/impact_result/drift_result
    are the *real*, unmodified Commit #3/#5/#9/#12 result objects --
    embedded verbatim, never re-summarized or re-derived -- the same
    "embed full source objects" convention every result type in this
    whole risk lineage already keeps. Each is None only when the stage
    that would have produced it was never reached (Rule: "a failed
    prerequisite stops dependent operations") or does not apply to the
    entry point that produced this result (e.g. approve_and_rollout()
    delegates its own pre-flight re-verification to Commit #6/#11's own
    already-established gates rather than re-running Commit #3/#5 a
    third time).

    approval_status/rollout_status are plain status strings read
    verbatim from Commit #10's own RiskProfileApproval.status / Commit
    #11's own RiskProfileRollout.state -- never a second vocabulary.

    governance_state is this class's own rollup (see module docstring),
    derived entirely from the fields above; blocking_reasons lists every
    concrete reason progress stopped (validation issues, compatibility
    reasons, impact blocking_conflicts, an unapproved approval, or a
    rollout failure reason), empty exactly when nothing blocked
    anything; warnings lists non-blocking evidence (impact-analysis/
    drift-detection warnings) that never stopped progress on its own.

    Zero side effects: constructing one never mutates, persists,
    activates, or rolls back anything -- it is a plain snapshot of
    already-computed evidence.
    """

    profile_id: str
    version: Optional[int]
    scope_id: str
    validation_result: object
    compatibility_result: object
    impact_result: object
    approval_status: Optional[str]
    rollout_status: Optional[str]
    drift_result: object
    governance_state: str
    blocking_reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "scope_id": self.scope_id,
            "validation_result": self.validation_result.to_dict() if self.validation_result is not None else None,
            "compatibility_result": (
                self.compatibility_result.to_dict() if self.compatibility_result is not None else None
            ),
            "impact_result": self.impact_result.to_dict() if self.impact_result is not None else None,
            "approval_status": self.approval_status,
            "rollout_status": self.rollout_status,
            "drift_result": self.drift_result.to_dict() if self.drift_result is not None else None,
            "governance_state": self.governance_state,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "evaluated_at": self.evaluated_at.isoformat(),
        }
