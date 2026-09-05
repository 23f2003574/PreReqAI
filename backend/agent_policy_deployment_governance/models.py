from dataclasses import asdict, dataclass, field
from typing import Optional

# Three closed decisions -- deliberately never a fourth: this series'
# Commit #10 LLMAgentPolicyDeploymentRollbackService already exists to
# actually perform a rollback, and this class never calls it (see Rules:
# "do not perform rollback automatically") -- ROLLBACK_RECOMMENDED is
# advice for a human/operator, never an action taken here.
KEEP = "keep"
INVESTIGATE = "investigate"
ROLLBACK_RECOMMENDED = "rollback_recommended"
DECISIONS = frozenset({KEEP, INVESTIGATE, ROLLBACK_RECOMMENDED})


@dataclass(frozen=True)
class GovernanceResult:
    """evaluate()'s complete, deterministic, read-only decision for one
    deployment_id.

    decision is never KEEP when verification failed ("a failed
    verification must never produce keep" holds by construction: see
    LLMAgentPolicyDeploymentGovernance.evaluate(), which only ever
    reaches its KEEP branch after Commit #9's own verification has
    already succeeded). reasons lists every fact the decision was built
    from, never just the conclusion. provenance carries the complete,
    already-serialized Commit #9 VerificationResult and Commit #11
    HealthResult this decision reused verbatim, plus how many earlier
    successful deployments (if any) exist for the same scope/template
    slot -- the evidence "inspect relevant deployment history"
    contributes toward INVESTIGATE vs. ROLLBACK_RECOMMENDED.

    scope_id/policy_id/template_id are preserved exactly as Commit #8's
    own deployment record carries them (None only when the record itself
    could not be found at all -- "missing evidence must be explicit, not
    guessed").

    No timestamp: evaluate() is a pure function of already-durable
    Commit #7-#11 state, so two calls against unchanged state produce
    two equal GovernanceResults, the same choice every other pure
    read-only checker in this series already makes.
    """

    deployment_id: str
    decision: str
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    scope_id: Optional[str] = None
    policy_id: Optional[str] = None
    template_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
