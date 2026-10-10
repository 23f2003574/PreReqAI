from backend.agent_policy_engine import InvalidPolicyRuleError, LLMAgentPolicyRule
from backend.agent_policy_templates import LLMAgentPolicyTemplate

# Commit #1's own placeholder-discovery helper, reused verbatim rather
# than a second implementation -- the same "reach into a sibling
# module's own private helper rather than duplicate its logic" precedent
# already established in the underlying agent_policy_* series (Commit #5
# reuses LLMAgentPolicyEvaluator._constraints_met the same way).
from backend.agent_policy_templates.service import _placeholders_in

from .models import ValidationIssue, ValidationResult

_SCALAR_PARAMETER_TYPES = (str, int, float, bool)


class LLMAgentPolicyTemplateValidator:
    """Deterministic, side-effect-free, pre-flight validation for Commit
    #1 policy templates -- run before persistence (validate()/
    validate_definition()) or before instantiate() (validate_parameters())
    to surface every problem in one pass, rather than the single
    first-failure Commit #1's own service already raises.

    Not a second policy validator: rule-shape checking is delegated
    entirely to Commit #1's own backend.agent_policy_engine.LLMAgentPolicyRule
    (via from_dict(), the exact same construction Commit #1's own
    LLMAgentPolicyTemplateService._validate_definition() already performs)
    and parameter discovery is delegated entirely to Commit #1's own
    _placeholders_in() -- this class adds no new rule-shape or
    placeholder-discovery logic of its own, only the "collect every
    issue instead of raising on the first one" reporting Commit #1
    itself deliberately does not attempt (create()/update() must fail
    fast to keep a bad record from ever being persisted; a validator
    meant to be called *before* that, on a draft, has no such
    constraint).

    None of validate()/validate_definition()/validate_parameters() ever
    persists, registers, or mutates anything -- they accept plain
    values (an in-memory LLMAgentPolicyTemplate that may not even be
    persisted yet, a raw policy_definition dict, or a parameters dict)
    and return a ValidationResult, nothing else.
    """

    def validate(self, template) -> ValidationResult:
        """Every problem with template as a whole: its own name/
        description fields, plus everything validate_definition() would
        find in its policy_definition."""
        issues = []

        if not isinstance(template, LLMAgentPolicyTemplate):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_template_type",
                        message=f"template must be an LLMAgentPolicyTemplate, got {type(template).__name__}",
                    )
                ]
            )

        if not template.name or not isinstance(template.name, str):
            issues.append(ValidationIssue(code="missing_name", message="name is required", path="name"))
        if not template.description or not isinstance(template.description, str):
            issues.append(
                ValidationIssue(code="missing_description", message="description is required", path="description")
            )

        definition_result = self.validate_definition(template.policy_definition)
        for issue in definition_result.issues:
            prefixed_path = "policy_definition" if issue.path is None else f"policy_definition.{issue.path}"
            issues.append(ValidationIssue(code=issue.code, message=issue.message, path=prefixed_path))

        return ValidationResult(issues=issues)

    def validate_definition(self, policy_definition) -> ValidationResult:
        """Every problem found in policy_definition on its own: missing/
        malformed name_template, missing/empty/malformed rules, an
        embedded scope_id (templates must stay scope-safe, per Commit
        #1), or a duplicated rule_id."""
        if not isinstance(policy_definition, dict):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_definition_type",
                        message=f"policy_definition must be a dict, got {type(policy_definition).__name__}",
                    )
                ]
            )

        issues = []

        if "scope_id" in policy_definition:
            issues.append(
                ValidationIssue(
                    code="embedded_scope_id",
                    message="policy_definition must not embed a scope_id -- templates must stay "
                    "scope-safe, reusable across every scope",
                    path="scope_id",
                )
            )

        name_template = policy_definition.get("name_template")
        if not name_template or not isinstance(name_template, str):
            issues.append(
                ValidationIssue(
                    code="missing_name_template", message="name_template is required", path="name_template"
                )
            )

        rules = policy_definition.get("rules")
        if not rules or not isinstance(rules, list):
            issues.append(
                ValidationIssue(code="missing_rules", message="rules is required and must be a non-empty list", path="rules")
            )
        else:
            seen_ids = set()
            for index, rule in enumerate(rules):
                path = f"rules[{index}]"
                if not isinstance(rule, dict):
                    issues.append(
                        ValidationIssue(
                            code="invalid_rule_type", message=f"each rule must be a dict, got {type(rule).__name__}", path=path
                        )
                    )
                    continue

                try:
                    resolved_rule = LLMAgentPolicyRule.from_dict(rule)
                except TypeError as error:
                    issues.append(ValidationIssue(code="invalid_rule_shape", message=str(error), path=path))
                    continue
                except InvalidPolicyRuleError as error:
                    issues.append(ValidationIssue(code="invalid_rule", message=str(error), path=path))
                    continue

                if resolved_rule.rule_id in seen_ids:
                    issues.append(
                        ValidationIssue(
                            code="duplicate_rule_id",
                            message=f"rule_id {resolved_rule.rule_id!r} is duplicated within this template",
                            path=f"{path}.rule_id",
                        )
                    )
                seen_ids.add(resolved_rule.rule_id)

        return ValidationResult(issues=issues)

    def validate_parameters(self, template, parameters) -> ValidationResult:
        """Every problem with instantiating template using parameters:
        a non-dict parameters argument, a parameter the template's own
        definition references but parameters does not supply, a
        parameter parameters supplies but the definition never
        references, or a parameter value that is not a plain scalar
        (str/int/float/bool) -- the only kinds of value that substitute
        cleanly into a "{name}" placeholder without producing a mangled
        string representation of a dict/list, or a nonsensical "None".

        A ValidationResult this method reports as valid means
        LLMAgentPolicyTemplateService.instantiate() will not raise any
        of MissingTemplateParameterError/UnexpectedTemplateParameterError/
        InvalidTemplateParametersError for this exact (template,
        parameters) pair -- it never re-derives that guarantee by calling
        instantiate() itself, only by running the identical checks ahead
        of time.
        """
        if not isinstance(template, LLMAgentPolicyTemplate):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_template_type",
                        message=f"template must be an LLMAgentPolicyTemplate, got {type(template).__name__}",
                    )
                ]
            )

        if not isinstance(parameters, dict):
            return ValidationResult(
                issues=[
                    ValidationIssue(
                        code="invalid_parameters_type",
                        message=f"parameters must be a dict, got {type(parameters).__name__}",
                    )
                ]
            )

        issues = []
        declared = _placeholders_in(template.policy_definition)
        given = set(parameters.keys())

        for name in sorted(declared - given):
            issues.append(
                ValidationIssue(
                    code="missing_parameter", message=f"parameter {name!r} is required by this template", path=f"parameters.{name}"
                )
            )
        for name in sorted(given - declared):
            issues.append(
                ValidationIssue(
                    code="unknown_parameter",
                    message=f"parameter {name!r} is not referenced by this template",
                    path=f"parameters.{name}",
                )
            )
        for name in sorted(given & declared):
            value = parameters[name]
            if isinstance(value, _SCALAR_PARAMETER_TYPES):
                continue
            issues.append(
                ValidationIssue(
                    code="invalid_parameter_value",
                    message=f"parameter {name!r} must be a plain string/number/boolean, got {type(value).__name__}",
                    path=f"parameters.{name}",
                )
            )

        return ValidationResult(issues=issues)
