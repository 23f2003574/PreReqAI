from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

# Two closed outcomes for a deploy() call -- the same plain-string
# status vocabulary Commit #1 (base series)'s own ACTIVE/ARCHIVED already
# uses, rather than a new Enum type. DEPLOYED is a genuine new activation
# (this exact policy_id was not already the deployed one for its
# scope/template family); ALREADY_DEPLOYED is deploy()'s own idempotent
# replay of a policy_id that already was -- never a failure, and never a
# second archive/record cycle.
DEPLOYED = "deployed"
ALREADY_DEPLOYED = "already_deployed"
STATUSES = frozenset({DEPLOYED, ALREADY_DEPLOYED})


@dataclass(frozen=True)
class DeploymentResult:
    """deploy()'s complete, provenance-preserving outcome for one
    (policy_id, target_context) call.

    template_id/template_version are the resolved Commit #1 template
    that actually produced policy_id (via Commit #6's own instantiation
    provenance) -- never the raw LLMAgentPolicy itself, which carries no
    template lineage of its own. previous_policy_id is the policy_id
    this deployment superseded for the same (scope_id, template name)
    pair, or None when this was the first deployment for it -- populated
    only once that previous policy has actually been archived (see
    LLMAgentPolicyTemplateDeploymentService: archiving happens strictly
    after every earlier gate already passed, so a DeploymentResult is
    only ever returned for a deployment that genuinely completed).

    Idempotent replay (status == ALREADY_DEPLOYED) carries the same
    deployment_id/deployed_at as the original deploy() call that first
    activated this policy_id -- never a fresh timestamp -- so a caller
    can tell a true repeat from a new activation. provenance() always
    returns the canonical record for a policy_id with status DEPLOYED
    (it genuinely is deployed); ALREADY_DEPLOYED only ever appears as
    deploy()'s own per-call return value on a repeat.
    """

    deployment_id: str
    policy_id: str
    scope_id: str
    template_id: str
    template_version: int
    status: str
    previous_policy_id: Optional[str]
    deployed_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["deployed_at"] = self.deployed_at.isoformat()
        return data
