from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class TemplateInstantiationPipelineRecord:
    """One immutable, append-only record of a single
    LLMAgentPolicyTemplateInstantiator.instantiate() call -- the only
    place this pipeline's own provenance lives, since the resulting
    LLMAgentPolicy itself gains no new field, and Commit #1's own
    LLMAgentPolicyTemplateInstantiation (recorded automatically by the
    underlying LLMAgentPolicyTemplateService.instantiate() this pipeline
    delegates to) only ever knows about resolved_template_id -- never
    the originally *requested* template_id when Commit #5's migrator
    substituted a freshly migrated one first.

    requested_template_id is exactly what the caller passed to
    instantiate(); resolved_template_id is the template actually used to
    materialize the policy -- equal to requested_template_id unless
    migrated is True, in which case it is the new template_id Commit
    #5's LLMAgentPolicyTemplateMigrator produced. current_version, when
    populated, is Commit #11 (base series)'s own
    LLMAgentPolicyVersionService's answer for policy_id immediately
    after creation -- populated only when this pipeline was given a
    version_service, never computed independently.
    """

    requested_template_id: str
    resolved_template_id: str
    target_version: Optional[int]
    migrated: bool
    scope_id: str
    policy_id: str
    parameters: dict
    current_version: Optional[int] = None
    pipeline_id: str = field(default_factory=lambda: str(uuid4()))
    instantiated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["instantiated_at"] = self.instantiated_at.isoformat()
        return data
