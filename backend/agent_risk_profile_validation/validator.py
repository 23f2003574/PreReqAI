from backend.agent_policy_risk_assessment import LEVELS
from backend.agent_risk_profile import (
    STATUSES,
    InvalidRiskProfileActionRuleError,
    LLMAgentRiskProfile,
    RiskProfileActionRule,
    resolve_level,
)

from .models import ValidationIssue, ValidationResult


class LLMAgentRiskProfileValidator:
    """Deterministic, side-effect-free, pre-flight validation for Commit
    #1 risk profiles -- run before persistence (validate()) or before
    resolution (validate_action_rules()) to surface every problem in
    one pass, rather than the single first-failure Commit #1's own
    LLMAgentRiskProfileService already raises.

    Not a second validation framework and not a new schema language:
    action_rule shape-checking is delegated entirely to Commit #1's own
    backend.agent_risk_profile.RiskProfileActionRule (via from_dict(),
    the exact same construction LLMAgentRiskProfileService's own
    _validate_action_rules() already performs), the supported risk
    level vocabulary is Commit #1's own imported
    backend.agent_policy_risk_assessment.LEVELS (never a second,
    locally-invented list of "known" levels), and
    validate_action_rules() resolves via Commit #1/#2's own
    resolve_level() -- the exact same {field: expected}
    matching/default_level fallback every other commit in this series
    already uses, never a duplicate copy of it. This class adds no new
    rule-shape, level-vocabulary, or matching logic of its own, only
    the "collect every issue instead of raising on the first one"
    reporting Commit #1 itself deliberately does not attempt (create()/
    update() must fail fast to keep a bad record from ever being
    persisted; a validator meant to be called *before* that, on a
    draft, has no such constraint) -- mirrors
    backend.agent_policy_template_validation.LLMAgentPolicyTemplateValidator's
    own validate()/validate_definition() split one series over.

    Neither validate() nor validate_action_rules() ever persists,
    archives, or mutates anything -- they accept plain values (an
    in-memory LLMAgentRiskProfile that may not even be persisted yet,
    and an action_context dict) and return a ValidationResult, nothing
    else. Neither calls an LLM.
    """

    def validate(self, profile) -> ValidationResult:
        """Every structural problem with profile as a whole: missing
        scope_id/name, an out-of-vocabulary status or default_level, a
        non-positive version, a conflicting action_name/action_category
        binding, and every problem within action_rules (malformed
        shape, an unknown risk level, or a duplicated rule_id).

        A ValidationResult this method reports as valid means
        LLMAgentRiskProfileService.create()/update() would accept an
        equivalent profile without raising -- it never re-derives that
        guarantee by calling create()/update() itself, only by running
        equivalent checks ahead of time (Rule: "Invalid profiles cannot
        be persisted").
        """
        if not isinstance(profile, LLMAgentRiskProfile):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_profile_type",
                        message=f"profile must be an LLMAgentRiskProfile, got {type(profile).__name__}",
                    )
                ]
            )

        issues = []

        if not profile.scope_id or not isinstance(profile.scope_id, str):
            issues.append(
                ValidationIssue(code="missing_scope_id", message="scope_id is required", path="scope_id")
            )
        if not profile.name or not isinstance(profile.name, str):
            issues.append(ValidationIssue(code="missing_name", message="name is required", path="name"))

        if profile.status not in STATUSES:
            issues.append(
                ValidationIssue(
                    code="invalid_status",
                    message=f"status {profile.status!r} is not one of {sorted(STATUSES)}",
                    path="status",
                )
            )

        if (
            not isinstance(profile.version, int)
            or isinstance(profile.version, bool)
            or profile.version < 1
        ):
            issues.append(
                ValidationIssue(
                    code="invalid_version",
                    message=f"version must be a positive integer, got {profile.version!r}",
                    path="version",
                )
            )

        if profile.default_level not in LEVELS:
            issues.append(
                ValidationIssue(
                    code="unknown_risk_level",
                    message=f"default_level {profile.default_level!r} is not one of {LEVELS}",
                    path="default_level",
                )
            )

        if profile.action_name is not None and (
            not isinstance(profile.action_name, str) or not profile.action_name.strip()
        ):
            issues.append(
                ValidationIssue(
                    code="invalid_action_name",
                    message="action_name must be a non-empty string when given",
                    path="action_name",
                )
            )
        if profile.action_category is not None and (
            not isinstance(profile.action_category, str) or not profile.action_category.strip()
        ):
            issues.append(
                ValidationIssue(
                    code="invalid_action_category",
                    message="action_category must be a non-empty string when given",
                    path="action_category",
                )
            )
        if profile.action_name is not None and profile.action_category is not None:
            issues.append(
                ValidationIssue(
                    code="conflicting_action_binding",
                    message="a risk profile may bind to action_name or action_category, not both",
                    path="action_category",
                )
            )

        if not isinstance(profile.action_rules, list):
            issues.append(
                ValidationIssue(
                    code="invalid_action_rules_type",
                    message=f"action_rules must be a list, got {type(profile.action_rules).__name__}",
                    path="action_rules",
                )
            )
        else:
            seen_ids = set()
            for index, rule in enumerate(profile.action_rules):
                path = f"action_rules[{index}]"

                if isinstance(rule, RiskProfileActionRule):
                    # Already passed RiskProfileActionRule's own
                    # __post_init__ validation at construction time --
                    # its level is guaranteed to be one of LEVELS, so
                    # there is nothing further to check here.
                    resolved_rule = rule
                elif isinstance(rule, dict):
                    # Checked ahead of from_dict() so an unsupported
                    # level gets its own specific, actionable
                    # "unknown_risk_level" code -- from_dict()'s own
                    # __post_init__ would otherwise raise on the first
                    # problem it finds (which may not be the level) and
                    # collapse every kind of problem into one generic
                    # "malformed_action_rule".
                    level = rule.get("level")
                    if level not in LEVELS:
                        issues.append(
                            ValidationIssue(
                                code="unknown_risk_level",
                                message=f"level {level!r} is not one of {LEVELS}",
                                path=f"{path}.level",
                            )
                        )
                        continue

                    try:
                        resolved_rule = RiskProfileActionRule.from_dict(rule)
                    except TypeError as error:
                        issues.append(
                            ValidationIssue(code="malformed_action_rule", message=str(error), path=path)
                        )
                        continue
                    except InvalidRiskProfileActionRuleError as error:
                        issues.append(
                            ValidationIssue(code="malformed_action_rule", message=str(error), path=path)
                        )
                        continue
                else:
                    issues.append(
                        ValidationIssue(
                            code="invalid_action_rule_type",
                            message=f"each action_rule must be a RiskProfileActionRule or dict, got "
                            f"{type(rule).__name__}",
                            path=path,
                        )
                    )
                    continue

                if resolved_rule.rule_id in seen_ids:
                    issues.append(
                        ValidationIssue(
                            code="duplicate_rule_id",
                            message=f"rule_id {resolved_rule.rule_id!r} is duplicated within this profile",
                            path=f"{path}.rule_id",
                        )
                    )
                seen_ids.add(resolved_rule.rule_id)

        return ValidationResult(issues=issues)

    def validate_action_rules(self, profile, action_context) -> ValidationResult:
        """Every problem with resolving action_context against profile
        right now: every structural problem validate() would already
        find, plus (only once profile is otherwise structurally sound)
        confirmation that Commit #1/#2's own resolve_level() actually
        produces one of the supported risk levels for this exact
        (profile, action_context) pair -- the "resolution integration"
        this method's own name promises, reusing the real resolution
        function rather than re-deriving an equivalent answer.

        A structurally unsound profile is never run through
        resolve_level() at all (it may not even have real
        RiskProfileActionRule instances to match with) -- its
        validate() issues are returned as-is, since a profile that
        cannot even be persisted has nothing further worth checking
        about how it would resolve (Rule: "Invalid profiles cannot be
        persisted or resolved").

        Raises nothing: an invalid action_context is reported as a
        ValidationIssue, the same way every other problem is, rather
        than raising InvalidActionContextError the way
        LLMAgentRiskProfileService.resolve()/
        LLMAgentRiskProfileResolver.resolve() do -- this method is a
        pre-flight check, never itself a resolution call.
        """
        if not isinstance(profile, LLMAgentRiskProfile):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_profile_type",
                        message=f"profile must be an LLMAgentRiskProfile, got {type(profile).__name__}",
                    )
                ]
            )
        if not isinstance(action_context, dict):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_action_context_type",
                        message=f"action_context must be a dict, got {type(action_context).__name__}",
                    )
                ]
            )

        structural = self.validate(profile)
        if not structural.is_valid:
            return structural

        level, _matched_rule_id, _reason = resolve_level(profile, action_context)
        if level not in LEVELS:
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="unknown_risk_level",
                        message=f"resolved level {level!r} is not one of {LEVELS}",
                        path="resolved_level",
                    )
                ]
            )

        return ValidationResult(issues=[])
