from dataclasses import asdict, dataclass, field
from typing import Optional

# Closed set of outcomes for one orchestrator.deploy() call. Each name
# reports exactly which stage of the flow (deploy -> verify -> health ->
# governance -> rollback) is the reason the call ended where it did --
# "health/governance failures must not be hidden" holds because there is
# no single generic "failed" status that could paper over which stage
# actually disagreed.
DEPLOY_FAILED = "deploy_failed"
VERIFICATION_FAILED = "verification_failed"
DEGRADED = "degraded"
SUCCEEDED = "succeeded"
ROLLBACK_RECOMMENDED = "rollback_recommended"
ROLLED_BACK = "rolled_back"
ROLLBACK_FAILED = "rollback_failed"
STATUSES = frozenset(
    {DEPLOY_FAILED, VERIFICATION_FAILED, DEGRADED, SUCCEEDED, ROLLBACK_RECOMMENDED, ROLLED_BACK, ROLLBACK_FAILED}
)


@dataclass(frozen=True)
class DeploymentResult:
    """orchestrator.deploy()'s complete outcome -- every stage's own
    result exposed verbatim (deploy_result/verification/health/governance/
    rollback), never summarized away, so "expose each stage's result and
    provenance" holds literally: a caller can always inspect exactly
    what Commit #7/#9/#11/#12/#10 each independently produced, not just
    this class's own combined status/reasons.

    status is SUCCEEDED only when every stage agreed there was nothing
    to flag (deploy succeeded, verification passed, governance decided
    KEEP) -- "failed verification prevents successful completion" and
    "health/governance failures must not be hidden" both hold because
    status is derived strictly from those stages' own verdicts, never
    reported as SUCCEEDED merely because Commit #7's own deploy() call
    itself didn't raise.

    rollback is populated only when this orchestrator actually attempted
    one (an explicit rollback_authorization collaborator was configured,
    consulted, and returned True) -- never on ROLLBACK_RECOMMENDED alone,
    since that status means governance recommended a rollback but no
    authorization was configured (or it declined), and this orchestrator
    performs no rollback of its own initiative otherwise.
    """

    policy_id: Optional[str]
    scope_id: Optional[str]
    status: str
    deploy_result: object = None
    verification: object = None
    health: object = None
    governance: object = None
    rollback: object = None
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
