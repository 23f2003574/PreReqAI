from backend.agent_policy_engine import InvalidAgentPolicyError, LLMAgentPolicyService
from backend.agent_policy_template_validation import LLMAgentPolicyTemplateValidator
from backend.agent_policy_templates import LLMAgentPolicyTemplate

from .models import CompatibilityResult


def _effects_used(policy_definition: dict) -> set:
    """Every distinct rule effect (Commit #1's own ALLOW/DENY vocabulary)
    a template's rules actually use -- the "required capabilities" a
    target runtime must support to honor this template's rules exactly
    as written."""
    rules = policy_definition.get("rules") or []
    return {rule.get("effect") for rule in rules if isinstance(rule, dict) and rule.get("effect")}


def _match_fields_used(policy_definition: dict) -> set:
    """Every distinct match-condition field name a template's rules
    reference (e.g. "tool_name") -- the "referenced rules/features" a
    target runtime must recognize to evaluate this template's rules."""
    fields = set()
    for rule in policy_definition.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match")
        if isinstance(match, dict):
            fields.update(match.keys())
    return fields


class LLMAgentPolicyTemplateCompatibility:
    """Deterministic, side-effect-free pre-flight compatibility gate: is
    it safe to instantiate this Commit #1 template against a given
    runtime/scope, before instantiate() is ever called.

    Not a second compatibility framework: this class introduces no new
    schema-version registry, capability-negotiation protocol, or rule
    validator of its own.

      - "policy schema/version" is checked against
        MIN_SUPPORTED_SCHEMA_VERSION, the same
        SUPPORTED_FORMAT/SUPPORTED_SCHEMA_VERSION class-constant pattern
        backend.session.research_snapshot_validator.ResearchSnapshotValidator
        already uses for its own format gate -- a target_context
        declaring its own current policy_schema_version at or above this
        floor is compatible (a "compatible version upgrade"); anything
        below it is not.
      - "required capabilities" and "referenced rules/features" are both
        derived purely by introspecting a template's own, already-
        persisted policy_definition (_effects_used()/_match_fields_used()
        above) -- never a new field bolted onto Commit #1's
        LLMAgentPolicyTemplate (whose policy_definition, per Commit #1's
        own _validate_definition(), only ever keeps "name_template" and
        "rules" -- anything else would be silently dropped on
        create()/update(), so no new persisted metadata was invented
        here). A target_context that does not declare
        "supported_effects"/"supported_match_fields" at all is treated
        as imposing no restriction on that axis (nothing to be
        incompatible with).
      - "target scope configuration" reuses Commit #1 (base series)'s
        own LLMAgentPolicyService._validate_scope_id() verbatim on
        target_context["scope_id"] -- the exact same check
        instantiate() itself will eventually apply, run here only to
        surface the problem earlier, as a compatibility reason rather
        than a raised exception from deep inside instantiate().
      - "reuse existing policy validation after compatibility succeeds":
        only once every check above finds nothing wrong does check()
        additionally run Commit #3's own
        LLMAgentPolicyTemplateValidator.validate(template) and fold any
        of its issues into this result's own reasons -- composed, never
        reimplemented, and skipped entirely once a more fundamental
        runtime/scope incompatibility already exists (no point
        validating rule shape against a target that cannot even run
        this schema version).

    check() never mutates, transforms, persists, or "fixes" template or
    target_context in any way -- an incompatible definition is reported,
    never silently downgraded, and calling check() twice with the same
    arguments always returns an equal CompatibilityResult (aside from
    object identity), the same input always producing the same verdict.
    """

    MIN_SUPPORTED_SCHEMA_VERSION = 1

    def __init__(self, validator: LLMAgentPolicyTemplateValidator = None):
        self._validator = validator if validator is not None else LLMAgentPolicyTemplateValidator()

    def check(self, template, target_context) -> CompatibilityResult:
        template_id = template.template_id if isinstance(template, LLMAgentPolicyTemplate) else None
        template_version = template.version if isinstance(template, LLMAgentPolicyTemplate) else None

        reasons = []
        provenance = {}

        if not isinstance(template, LLMAgentPolicyTemplate):
            reasons.append(f"template must be an LLMAgentPolicyTemplate, got {type(template).__name__}")
        if not isinstance(target_context, dict):
            reasons.append(f"target_context must be a dict, got {type(target_context).__name__}")

        if reasons:
            return CompatibilityResult(
                template_id=template_id, template_version=template_version, compatible=False, reasons=reasons,
                provenance=provenance,
            )

        policy_definition = template.policy_definition if isinstance(template.policy_definition, dict) else {}

        requested_schema_version = target_context.get("policy_schema_version", self.MIN_SUPPORTED_SCHEMA_VERSION)
        provenance["policy_schema_version"] = requested_schema_version
        provenance["min_supported_schema_version"] = self.MIN_SUPPORTED_SCHEMA_VERSION
        if not isinstance(requested_schema_version, int) or isinstance(requested_schema_version, bool) or (
            requested_schema_version < self.MIN_SUPPORTED_SCHEMA_VERSION
        ):
            reasons.append(
                f"policy schema version {requested_schema_version!r} is not supported "
                f"(minimum supported is {self.MIN_SUPPORTED_SCHEMA_VERSION})"
            )

        required_capabilities = _effects_used(policy_definition)
        supported_effects = target_context.get("supported_effects")
        missing_capabilities = (
            required_capabilities - set(supported_effects) if supported_effects is not None else set()
        )
        provenance["required_capabilities"] = sorted(required_capabilities)
        provenance["missing_capabilities"] = sorted(missing_capabilities)
        for capability in sorted(missing_capabilities):
            reasons.append(f"target does not support required capability (effect): {capability!r}")

        referenced_features = _match_fields_used(policy_definition)
        supported_match_fields = target_context.get("supported_match_fields")
        unsupported_features = (
            referenced_features - set(supported_match_fields) if supported_match_fields is not None else set()
        )
        provenance["referenced_features"] = sorted(referenced_features)
        provenance["unsupported_features"] = sorted(unsupported_features)
        for feature in sorted(unsupported_features):
            reasons.append(f"target does not support referenced rule feature: {feature!r}")

        scope_id = target_context.get("scope_id")
        provenance["scope_id"] = scope_id
        try:
            LLMAgentPolicyService._validate_scope_id(scope_id)
        except InvalidAgentPolicyError as error:
            reasons.append(f"invalid target scope configuration: {error}")

        if not reasons:
            validation_result = self._validator.validate(template)
            provenance["validation_issue_count"] = len(validation_result.issues)
            for issue in validation_result.issues:
                located = f" ({issue.path})" if issue.path else ""
                reasons.append(f"{issue.code}: {issue.message}{located}")

        return CompatibilityResult(
            template_id=template_id,
            template_version=template_version,
            compatible=not reasons,
            reasons=reasons,
            provenance=provenance,
        )
