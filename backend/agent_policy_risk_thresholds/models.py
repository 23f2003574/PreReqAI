from dataclasses import dataclass

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVELS

# Action vocabulary: ALLOW/DENY are Commit #1 (base series)'s own
# LLMAgentPolicy effect constants, reused as-is rather than redefined --
# "support the repository's existing action semantics" for the two ends
# of the spectrum this repo already names. REVIEW is new: nothing in the
# repository already has a three-way allow/escalate/deny vocabulary
# (backend.session.execution_policy_risk_threshold's own ACTION_ALLOW/
# WARN/BLOCK is the closest analog, but a different domain's own
# constants, not reusable here), so this is the minimal middle value the
# goal's own fallback ("if none exist... allow | review | deny")
# sanctions.
REVIEW = "REVIEW"
ACTIONS = (ALLOW, REVIEW, DENY)

# Default per-scope thresholds when a scope has never called set(): only
# HIGH and CRITICAL warrant anything beyond normal execution, mirroring
# how conservative a brand-new, unconfigured scope should be without a
# project having opted into anything stricter.
DEFAULT_REVIEW_AT = LEVEL_HIGH
DEFAULT_DENY_AT = LEVEL_CRITICAL


class InvalidRiskThresholdsError(ValueError):
    """Raised when a RiskThresholds' fields are missing, invalid, or
    out of order."""


@dataclass(frozen=True)
class RiskThresholds:
    """One scope's configurable mapping from Commit #1's own
    LEVEL_LOW/MEDIUM/HIGH/CRITICAL severity to an enforcement action.

    review_at and deny_at are each a *minimum* level (inclusive) --
    review_at is the lowest severity at which REVIEW applies, deny_at
    the lowest at which DENY applies. Anything below review_at is
    ALLOW. This operates purely on Commit #1/#2's own already-computed
    LEVELS ordinal position, never a raw numeric score -- Commit #2's
    entire purpose was normalizing risk into these four levels for
    downstream governance to consume, so thresholding at the level
    Commit #2 already reports is what "build on Commit #1-#2" means
    here, rather than reintroducing a score Commit #2 deliberately does
    not expose.

    Because LEVEL_CRITICAL is always the highest-ordinal entry in
    LEVELS, deny_at's own ordinal position can never exceed it for any
    valid RiskThresholds -- a CRITICAL classification therefore always
    resolves to DENY, for every possible (validly-ordered) threshold
    configuration. This is what makes "explicit policy denial remains
    authoritative" hold by construction: Commit #1 already guarantees
    an explicit policy deny always produces risk_level=CRITICAL (its
    own policy_denial factor is weighted at MAX_SCORE), so no project
    configuration can ever water that down to ALLOW or REVIEW.

    A value object only -- performs no evaluation itself; deciding which
    RiskAction a classification maps to is
    LLMAgentPolicyRiskThresholdService.evaluate()'s job.

    Deliberately carries no timestamp: two get() calls for the same
    never-configured scope must be `==`, the same determinism discipline
    RiskAssessment/RiskClassification before it already established (see
    Rules: "Deterministic boundary behavior") -- a per-write timestamp
    would make even an unmodified default compare unequal to itself
    across calls.
    """

    scope_id: str
    review_at: str = DEFAULT_REVIEW_AT
    deny_at: str = DEFAULT_DENY_AT

    def __post_init__(self):
        if not self.scope_id or not isinstance(self.scope_id, str):
            raise InvalidRiskThresholdsError("scope_id is required and must be a non-empty string")

        if self.review_at not in LEVELS:
            raise InvalidRiskThresholdsError(
                f"review_at {self.review_at!r} is not one of {LEVELS}"
            )
        if self.deny_at not in LEVELS:
            raise InvalidRiskThresholdsError(f"deny_at {self.deny_at!r} is not one of {LEVELS}")

        if LEVELS.index(self.deny_at) < LEVELS.index(self.review_at):
            raise InvalidRiskThresholdsError(
                f"deny_at ({self.deny_at!r}) must be at or above review_at ({self.review_at!r}) "
                f"in severity; thresholds must be ordered allow < review <= deny"
            )

    def to_dict(self) -> dict:
        return {"scope_id": self.scope_id, "review_at": self.review_at, "deny_at": self.deny_at}

    @classmethod
    def from_dict(cls, data: dict) -> "RiskThresholds":
        return cls(**data)


@dataclass(frozen=True)
class RiskAction:
    """LLMAgentPolicyRiskThresholdService.evaluate()'s outcome for one
    Commit #2 RiskClassification against one scope's RiskThresholds.

    Never mutates the classification it was computed from -- action is
    derived purely by comparing classification.risk_level's ordinal
    position against the resolved RiskThresholds (see RiskThresholds'
    own docstring for why this makes an explicit policy denial always
    resolve to DENY). provenance embeds both the source classification
    and the thresholds evaluated against, verbatim, so the decision is
    always traceable back to exactly what produced it -- the same
    "embed a prior commit's full result, never re-summarize" convention
    this series' own RiskClassification.provenance already established.
    """

    action: str
    scope_id: str
    risk_level: str
    reason: str
    provenance: dict
