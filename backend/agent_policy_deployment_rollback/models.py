from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_policy_deployment_verification import VerificationResult

# Two closed outcomes for one rollback() call -- the same plain-string
# status vocabulary this series already uses everywhere else. Neither
# implies a failure: ALREADY_CURRENT is rollback()'s own idempotent
# no-op outcome, never an error.
ROLLED_BACK = "rolled_back"
ALREADY_CURRENT = "already_current"
STATUSES = frozenset({ROLLED_BACK, ALREADY_CURRENT})


@dataclass(frozen=True)
class RollbackResult:
    """rollback()'s complete, provenance-preserving outcome for one
    (deployment_id, reason) call.

    target_deployment_id/target_policy_id/target_template_version
    describe the deployment being restored *to*; source_deployment_id/
    source_policy_id/source_template_version describe whatever deployment
    previously occupied that (scope, template) slot, or are all None
    when there was nothing to supersede (a first-ever deployment) or
    this call turned out to be a no-op (status == ALREADY_CURRENT).
    policy_id is the policy_id actually ACTIVE for the slot once this
    call returns -- the freshly re-instantiated one on a genuine
    rollback, or the already-current one unchanged on an idempotent
    replay.

    verification is Commit #9's own VerificationResult for the restored
    state, always populated (never None) -- rollback() never returns
    normally without it, so "verify restored state" is not something a
    caller can forget to also do.

    reason/actor are preserved verbatim, exactly as given to rollback().
    """

    target_deployment_id: str
    target_policy_id: str
    policy_id: str
    scope_id: str
    template_id: str
    status: str
    reason: str
    verification: VerificationResult
    target_template_version: Optional[int] = None
    source_deployment_id: Optional[str] = None
    source_policy_id: Optional[str] = None
    source_template_version: Optional[int] = None
    actor: Optional[str] = None
    rollback_id: str = field(default_factory=lambda: str(uuid4()))
    rolled_back_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["rolled_back_at"] = self.rolled_back_at.isoformat()
        return data
