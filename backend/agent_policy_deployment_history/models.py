from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Two closed outcomes for one deployment attempt -- the same plain-
# string status vocabulary this series (and the base agent_policy_*
# series before it) already uses everywhere else, rather than a new
# Enum type. Both are recorded through the exact same record() call;
# neither implies the other was ever attempted.
DEPLOYMENT_SUCCEEDED = "deployment_succeeded"
DEPLOYMENT_FAILED = "deployment_failed"
STATUSES = frozenset({DEPLOYMENT_SUCCEEDED, DEPLOYMENT_FAILED})


@dataclass(frozen=True)
class LLMAgentPolicyDeploymentRecord:
    """One immutable, append-only snapshot of a single Commit #7
    deploy() attempt -- successful or failed.

    Deliberately a compact, reference-based record, the same "what is
    deliberately absent" discipline
    backend.agent_policy_audit.LLMAgentPolicyDecisionAudit already
    established for this series' other decision trail: template_id/
    template_version/policy_version are bare identifiers/numbers, never
    a copy of a template's or policy's own rules -- correlating this
    record back to the actual rule content that was (or would have
    been) deployed always goes back through Commit #1-#7's own already-
    durable records, by id, never duplicated here. provenance is a
    small, JSON-safe dict of contextual detail (e.g. a redacted failure
    reason, or the previous policy_id a successful deployment
    superseded) -- never the policy/template payload itself.

    Never updated or deleted once recorded -- LLMAgentPolicyDeploymentHistory.
    record() only ever appends a new LLMAgentPolicyDeploymentRecord, the
    same append-only discipline every other audit/history trail in this
    repository already keeps.

    Attributes:
        deployment_id: For a DEPLOYMENT_SUCCEEDED record, exactly the
            real Commit #7 DeploymentResult.deployment_id it observed --
            never a second, independently-generated id for the same
            successful deployment. For a DEPLOYMENT_FAILED record (no
            DeploymentResult was ever produced, since deploy() itself
            raised), a fresh id of this record's own.
        policy_id: The policy_id deploy() was called with
        template_id: The Commit #1 template that produced policy_id, or
            None if it could not even be resolved (e.g. policy_id itself
            was unknown or had no Commit #6 provenance)
        template_version: That template's own Commit #1 .version field,
            or None under the same conditions as template_id
        target_scope: The scope_id this deployment targeted
        policy_version: Commit #11 (base series)'s own current version
            number for policy_id, or None when no version_service was
            configured to resolve one, or none exists yet
        status: One of STATUSES
        provenance: Contextual detail about this attempt -- never a
            policy/template payload
        reason: Why this deployment attempt happened, when the caller
            supplied one (e.g. Commit #10's own rollback records why it
            rolled back); None when not supplied. Added alongside
            Commit #10 as a purely additive field -- every record made
            before it existed simply has reason=None, exactly as if it
            had always been there, the same evolution
            backend.agent_policy_history.LLMAgentPolicyChange's own
            reason field (added alongside base-series Commit #12)
            already went through
        actor: Who or what made this deployment attempt, when known;
            None when not supplied. Same purely-additive history as
            reason
    """

    policy_id: str
    target_scope: str
    status: str
    template_id: Optional[str] = None
    template_version: Optional[int] = None
    policy_version: Optional[int] = None
    provenance: dict = field(default_factory=dict)
    reason: Optional[str] = None
    actor: Optional[str] = None
    deployment_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyDeploymentRecord":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
