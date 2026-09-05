from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class MigrationCheck:
    """can_migrate()'s complete, deterministic verdict for whether
    template can be migrated to target_version.

    template_id/source_version are always the template's own current
    identifiers (source_version is None only when template itself was
    not even a real LLMAgentPolicyTemplate, in which case nothing else
    could be checked either). reasons is empty when can_migrate is True,
    and otherwise lists every reason migration cannot proceed (an
    invalid source, an unsupported target version, or a backward
    transition) -- never just the first one, mirroring Commit #3/#4's
    own "collect everything in one pass" ValidationResult/
    CompatibilityResult shape.
    """

    template_id: Optional[str]
    source_version: Optional[int]
    target_version: Optional[int]
    can_migrate: bool
    reasons: list = field(default_factory=list)


@dataclass(frozen=True)
class LLMAgentPolicyTemplateMigrationRecord:
    """One immutable, append-only record of a single migrate() call --
    the only place a migrated template's lineage (which source
    template/version it came from, and which target version it was
    migrated to) is preserved, since the migrated
    LLMAgentPolicyTemplate itself is a completely ordinary Commit #1
    record with no notion of where it came from.

    Looked up by migrated_template_id via
    LLMAgentPolicyTemplateMigrator.provenance() -- the same "provenance
    lives in a separate, append-only side record keyed by the produced
    object's own id" shape Commit #1's own
    LLMAgentPolicyTemplateInstantiation already established for
    instantiate().
    """

    source_template_id: str
    source_version: int
    migrated_template_id: str
    target_version: int
    migration_id: str = field(default_factory=lambda: str(uuid4()))
    migrated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["migrated_at"] = self.migrated_at.isoformat()
        return data
