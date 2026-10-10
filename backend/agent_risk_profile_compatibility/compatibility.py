from backend.agent_risk_profile import InvalidRiskProfileError, LLMAgentRiskProfile, LLMAgentRiskProfileService
from backend.agent_risk_profile_resolution import TIER_ACTION_CATEGORY, TIER_EXACT_ACTION, TIER_SCOPE_DEFAULT
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator

from .models import CompatibilityResult


def _levels_used(profile: LLMAgentRiskProfile) -> set:
    """Every distinct risk level (Commit #1's own LEVEL_LOW/MEDIUM/HIGH/
    CRITICAL vocabulary) profile actually references -- its
    default_level plus every action_rule's own level -- the "required
    risk factors" a target runtime must recognize to honor this
    profile's resolutions exactly as written."""
    levels = {profile.default_level}
    levels.update(rule.level for rule in profile.action_rules)
    return levels


def _match_fields_used(profile: LLMAgentRiskProfile) -> set:
    """Every distinct match-condition field name profile's action_rules
    reference (e.g. "tool_name") -- the "referenced action types" a
    target runtime must recognize to evaluate this profile's rules."""
    fields = set()
    for rule in profile.action_rules:
        fields.update(rule.match.keys())
    return fields


def _specificity_tier(profile: LLMAgentRiskProfile) -> str:
    """Which of Commit #2's own three specificity tiers profile is
    bound to -- the one "capability" a target's own
    LLMAgentRiskProfileResolver must support to ever select this
    profile at all."""
    if profile.action_name is not None:
        return TIER_EXACT_ACTION
    if profile.action_category is not None:
        return TIER_ACTION_CATEGORY
    return TIER_SCOPE_DEFAULT


class LLMAgentRiskProfileCompatibility:
    """Deterministic, side-effect-free pre-flight compatibility gate: is
    it safe to activate this Commit #1 risk profile against a given
    agent/security/policy runtime, before it is ever relied on by
    LLMAgentRiskProfileResolver.

    Not a second compatibility framework: this class introduces no new
    schema-version registry, capability-negotiation protocol, or
    profile validator of its own -- mirrors
    backend.agent_policy_template_compatibility.LLMAgentPolicyTemplateCompatibility
    (this repository's only other profile/template-shaped compatibility
    gate) check-for-check:

      - "profile version/schema" is checked against
        MIN_SUPPORTED_SCHEMA_VERSION, the identical class-constant floor
        pattern that module already established -- a target_context
        declaring its own current risk_profile_schema_version at or
        above this floor is compatible; anything below it is not.
      - "referenced risk factors" and "action types/capabilities" are
        both derived purely by introspecting a profile's own,
        already-persisted action_rules/default_level
        (_levels_used()/_match_fields_used() above) plus its Commit #2
        action_name/action_category specificity binding
        (_specificity_tier()) -- never a new field bolted onto Commit
        #1's LLMAgentRiskProfile. A target_context that does not declare
        "supported_risk_levels"/"supported_match_fields"/
        "supported_tiers" at all is treated as imposing no restriction
        on that axis (nothing to be incompatible with) -- the identical
        "missing declaration means no restriction" rule the template
        precedent already established for its own supported_effects/
        supported_match_fields.
      - "policy/security integrations" reuses Commit #1's own
        LLMAgentRiskProfileService._validate_scope_id() verbatim on
        target_context["scope_id"] -- the exact same check
        create()/update()/resolve() themselves already apply, run here
        only to surface the problem earlier, as a compatibility reason
        rather than a raised exception -- plus one risk-profile-specific
        addition the template precedent has no analog for: a profile
        activated against a scope other than its own is never safe
        (Commit #1/#2's own scope-isolation guarantee would otherwise be
        silently bypassed), so target_context["scope_id"] must equal
        profile.scope_id.
      - "reuse existing validation after compatibility succeeds": only
        once every check above finds nothing wrong does check()
        additionally run Commit #3's own
        LLMAgentRiskProfileValidator.validate(profile) and fold any of
        its issues into this result's own reasons -- composed, never
        reimplemented, and skipped entirely once a more fundamental
        runtime/scope incompatibility already exists.

    check() never mutates, transforms, persists, activates, or "fixes"
    profile or target_context in any way -- an incompatible profile is
    reported, never silently downgraded or partially applied (Rule:
    "Never silently drop unsupported rules"), and calling check() twice
    with the same arguments always returns an equal CompatibilityResult
    (aside from object identity): the same input always produces the
    same verdict.
    """

    MIN_SUPPORTED_SCHEMA_VERSION = 1

    def __init__(self, validator: LLMAgentRiskProfileValidator = None):
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()

    def check(self, profile, target_context) -> CompatibilityResult:
        profile_id = profile.profile_id if isinstance(profile, LLMAgentRiskProfile) else None
        profile_version = profile.version if isinstance(profile, LLMAgentRiskProfile) else None

        reasons = []
        provenance = {}

        if not isinstance(profile, LLMAgentRiskProfile):
            reasons.append(f"profile must be an LLMAgentRiskProfile, got {type(profile).__name__}")
        if not isinstance(target_context, dict):
            reasons.append(f"target_context must be a dict, got {type(target_context).__name__}")

        if reasons:
            return CompatibilityResult(
                profile_id=profile_id, profile_version=profile_version, compatible=False, reasons=reasons,
                provenance=provenance,
            )

        requested_schema_version = target_context.get(
            "risk_profile_schema_version", self.MIN_SUPPORTED_SCHEMA_VERSION
        )
        provenance["risk_profile_schema_version"] = requested_schema_version
        provenance["min_supported_schema_version"] = self.MIN_SUPPORTED_SCHEMA_VERSION
        if (
            not isinstance(requested_schema_version, int)
            or isinstance(requested_schema_version, bool)
            or requested_schema_version < self.MIN_SUPPORTED_SCHEMA_VERSION
        ):
            reasons.append(
                f"risk profile schema version {requested_schema_version!r} is not supported "
                f"(minimum supported is {self.MIN_SUPPORTED_SCHEMA_VERSION})"
            )

        required_levels = _levels_used(profile)
        supported_levels = target_context.get("supported_risk_levels")
        missing_levels = required_levels - set(supported_levels) if supported_levels is not None else set()
        provenance["required_risk_levels"] = sorted(required_levels)
        provenance["missing_risk_levels"] = sorted(missing_levels)
        for level in sorted(missing_levels):
            reasons.append(f"target does not support required risk factor (level): {level!r}")

        referenced_fields = _match_fields_used(profile)
        supported_match_fields = target_context.get("supported_match_fields")
        unsupported_fields = (
            referenced_fields - set(supported_match_fields) if supported_match_fields is not None else set()
        )
        provenance["referenced_action_fields"] = sorted(referenced_fields)
        provenance["unsupported_action_fields"] = sorted(unsupported_fields)
        for field_name in sorted(unsupported_fields):
            reasons.append(f"target does not support referenced action type/field: {field_name!r}")

        required_tier = _specificity_tier(profile)
        supported_tiers = target_context.get("supported_tiers")
        provenance["required_tier"] = required_tier
        if supported_tiers is not None and required_tier not in supported_tiers:
            provenance["missing_tier"] = required_tier
            reasons.append(f"target does not support required specificity capability: {required_tier!r}")
        else:
            provenance["missing_tier"] = None

        scope_id = target_context.get("scope_id")
        provenance["scope_id"] = scope_id
        try:
            LLMAgentRiskProfileService._validate_scope_id(scope_id)
        except InvalidRiskProfileError as error:
            reasons.append(f"invalid target scope configuration: {error}")
        else:
            if scope_id != profile.scope_id:
                reasons.append(
                    f"profile is bound to scope {profile.scope_id!r}, not target scope {scope_id!r}"
                )

        if not reasons:
            validation_result = self._validator.validate(profile)
            provenance["validation_issue_count"] = len(validation_result.issues)
            for issue in validation_result.issues:
                located = f" ({issue.path})" if issue.path else ""
                reasons.append(f"{issue.code}: {issue.message}{located}")

        return CompatibilityResult(
            profile_id=profile_id,
            profile_version=profile_version,
            compatible=not reasons,
            reasons=reasons,
            provenance=provenance,
        )
