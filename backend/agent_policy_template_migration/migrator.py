from backend.agent_policy_template_compatibility import LLMAgentPolicyTemplateCompatibility
from backend.agent_policy_template_validation import LLMAgentPolicyTemplateValidator
from backend.agent_policy_templates import LLMAgentPolicyTemplate, LLMAgentPolicyTemplateService

from .models import LLMAgentPolicyTemplateMigrationRecord, MigrationCheck

# A synthetic, structural-only compatibility probe -- not a real scope.
# Deliberately imposes no capability/feature restriction (omits
# "supported_effects"/"supported_match_fields" entirely) so it can never
# itself reject a migrated definition on runtime-capability grounds; its
# only job is to satisfy Commit #4's own required "scope_id" shape so
# LLMAgentPolicyTemplateCompatibility.check() can run its composed
# Commit #3 rule validation against the migrated result, per this
# commit's own "run compatibility validation after migration" rule.
_STRUCTURAL_COMPATIBILITY_CONTEXT = {
    "policy_schema_version": LLMAgentPolicyTemplateCompatibility.MIN_SUPPORTED_SCHEMA_VERSION,
    "scope_id": "agent-policy-template-migration-check",
}


class UnsupportedTemplateMigrationError(ValueError):
    """Raised when migrate() is given a (template, target_version) pair
    can_migrate() has already found unmigrable -- an invalid source, an
    unsupported target version, or a backward transition. Every reason
    can_migrate() found is included, never just the first."""


class InvalidMigratedTemplateError(ValueError):
    """Raised when the migrated result itself fails Commit #4's
    post-migration compatibility/validation gate -- should not happen
    for either transformation this migrator actually performs (both are
    purely additive to an already-valid source), but is never silently
    ignored if it somehow does."""


class UnknownTemplateMigrationError(KeyError):
    """Raised when provenance() is given a migrated_template_id that was
    never produced by this migrator's own migrate()."""


class LLMAgentPolicyTemplateMigrator:
    """Controlled, deterministic migration of a Commit #1 policy template
    between the small, closed set of template schema versions this
    repository actually supports -- never a generic, open-ended version
    ladder.

    version here is Commit #1's own LLMAgentPolicyTemplate.version field
    (the same field Commit #2's registry already keys its own name/
    version index on) -- no second, independently-tracked version axis
    is introduced. SUPPORTED_VERSIONS = {1, 2} is this migrator's own
    closed, explicit statement of exactly which versions it knows how to
    reason about; a version outside that set, or a target below the
    source (no downgrade path), is rejected outright by can_migrate()
    rather than attempted.

    The only real transformation this migrator performs (version 1 ->
    2) touches exactly one already-existing Commit #1 rule field --
    reason -- filling a blank one in with an explicit, deterministic
    placeholder naming the rule it came from; every rule_id/effect/match
    is carried forward completely unchanged, and no rule is ever
    dropped, satisfying "never silently drop policy rules or
    parameters" by construction rather than by a separate check. A
    same-version "migration" (1->1, 2->2) is a pure identity copy,
    supported for idempotency the same way Commit #12 (base series)'s
    own rollback-to-current-version already is.

    migrate() never touches the source template: it only ever reads it,
    then calls Commit #1's own LLMAgentPolicyTemplateService.create()
    to persist the migrated result as a completely new, independent
    template_id -- reusing Commit #1's own definition validation
    verbatim ("validate the result"), never a second one. Once created,
    the result is re-checked through Commit #4's own
    LLMAgentPolicyTemplateCompatibility.check() (composing Commit #3's
    validator, per Commit #4's own "reuse existing policy validation
    after compatibility succeeds" rule) against a synthetic, capability-
    unrestricted probe context -- purely a defensive gate, since both of
    this migrator's own transformations are provably safe, but never
    skipped.

    Migration lineage (which source template/version produced which
    migrated template_id, and to which target version) is preserved in
    a separate, append-only LLMAgentPolicyTemplateMigrationRecord,
    looked up by the migrated template's own id via provenance() -- the
    same side-record shape Commit #1's own
    LLMAgentPolicyTemplateInstantiation already established, since the
    migrated LLMAgentPolicyTemplate itself (an entirely ordinary Commit
    #1 record) carries no lineage field of its own.
    """

    SUPPORTED_VERSIONS = frozenset({1, 2})

    def __init__(
        self,
        template_service: LLMAgentPolicyTemplateService,
        validator: LLMAgentPolicyTemplateValidator = None,
        compatibility=None,
    ):
        self._template_service = template_service
        self._validator = validator if validator is not None else LLMAgentPolicyTemplateValidator()
        self._compatibility = compatibility if compatibility is not None else LLMAgentPolicyTemplateCompatibility(
            self._validator
        )
        self._migrations_by_migrated_id: dict[str, LLMAgentPolicyTemplateMigrationRecord] = {}

    def can_migrate(self, template, target_version) -> MigrationCheck:
        """Whether template can be migrated to target_version -- every
        reason it cannot, never just the first."""
        template_id = template.template_id if isinstance(template, LLMAgentPolicyTemplate) else None
        source_version = template.version if isinstance(template, LLMAgentPolicyTemplate) else None
        reasons = []

        if not isinstance(template, LLMAgentPolicyTemplate):
            reasons.append(f"template must be an LLMAgentPolicyTemplate, got {type(template).__name__}")
        if not isinstance(target_version, int) or isinstance(target_version, bool):
            reasons.append(f"target_version must be an int, got {type(target_version).__name__}")

        if reasons:
            return MigrationCheck(
                template_id=template_id, source_version=source_version, target_version=None,
                can_migrate=False, reasons=reasons,
            )

        validation_result = self._validator.validate(template)
        for issue in validation_result.issues:
            located = f" ({issue.path})" if issue.path else ""
            reasons.append(f"invalid source template: {issue.code}: {issue.message}{located}")

        if source_version not in self.SUPPORTED_VERSIONS:
            reasons.append(
                f"source version {source_version} is not a supported template version "
                f"{sorted(self.SUPPORTED_VERSIONS)}"
            )
        if target_version not in self.SUPPORTED_VERSIONS:
            reasons.append(
                f"target version {target_version} is not a supported template version "
                f"{sorted(self.SUPPORTED_VERSIONS)}"
            )
        elif source_version in self.SUPPORTED_VERSIONS and target_version < source_version:
            reasons.append(f"cannot migrate backward from version {source_version} to {target_version}")

        return MigrationCheck(
            template_id=template_id, source_version=source_version, target_version=target_version,
            can_migrate=not reasons, reasons=reasons,
        )

    def migrate(self, template, target_version) -> LLMAgentPolicyTemplate:
        """Migrate template to target_version, returning the newly
        created, independent LLMAgentPolicyTemplate that resulted --
        template itself is never mutated.

        Raises:
            UnsupportedTemplateMigrationError: If can_migrate() found any
                reason this (template, target_version) pair cannot
                proceed
            InvalidMigratedTemplateError: If the migrated result somehow
                fails Commit #4's own post-migration compatibility gate
        """
        check = self.can_migrate(template, target_version)
        if not check.can_migrate:
            raise UnsupportedTemplateMigrationError(
                f"cannot migrate template {check.template_id!r} from version {check.source_version} "
                f"to version {target_version!r}: {'; '.join(check.reasons)}"
            )

        source_definition = template.policy_definition
        migrated_rules = self._transform_rules(source_definition["rules"], template.version, target_version)
        migrated_definition = {"name_template": source_definition["name_template"], "rules": migrated_rules}

        migrated = self._template_service.create(template.name, template.description, migrated_definition)

        compatibility_result = self._compatibility.check(migrated, _STRUCTURAL_COMPATIBILITY_CONTEXT)
        if not compatibility_result.compatible:
            raise InvalidMigratedTemplateError(
                f"migrated template {migrated.template_id!r} failed post-migration compatibility "
                f"validation: {'; '.join(compatibility_result.reasons)}"
            )

        record = LLMAgentPolicyTemplateMigrationRecord(
            source_template_id=template.template_id,
            source_version=template.version,
            migrated_template_id=migrated.template_id,
            target_version=target_version,
        )
        self._migrations_by_migrated_id[migrated.template_id] = record

        return migrated

    def provenance(self, migrated_template_id: str) -> LLMAgentPolicyTemplateMigrationRecord:
        """The LLMAgentPolicyTemplateMigrationRecord for
        migrated_template_id -- exactly which source template/version it
        was migrated from, and to which target version.

        Raises:
            UnknownTemplateMigrationError: If migrated_template_id was
                never produced by this migrator's own migrate()
        """
        record = self._migrations_by_migrated_id.get(migrated_template_id)
        if record is None:
            raise UnknownTemplateMigrationError(migrated_template_id)
        return record

    def _transform_rules(self, rules: list, source_version: int, target_version: int) -> list:
        if source_version == target_version:
            return [dict(rule) for rule in rules]
        if source_version == 1 and target_version == 2:
            return [self._fill_blank_reason(rule) for rule in rules]
        raise UnsupportedTemplateMigrationError(
            f"no repository-supported transformation from version {source_version} to {target_version}"
        )

    @staticmethod
    def _fill_blank_reason(rule: dict) -> dict:
        migrated_rule = dict(rule)
        if not migrated_rule.get("reason"):
            migrated_rule["reason"] = (
                f"(migrated from schema v1 -- no reason recorded for rule {migrated_rule.get('rule_id')!r})"
            )
        return migrated_rule
