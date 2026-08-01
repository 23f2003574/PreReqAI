from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity,
)


def _non_empty_members(templates, parameters) -> bool:
    return len(templates) > 0


def _unique_template_targets(templates, parameters) -> bool:
    template_ids = [template.template_id for template in templates]

    return len(set(template_ids)) == len(template_ids)


def _unique_parameter_names(templates, parameters) -> bool:
    names = [parameter.name for parameter in parameters]

    return len(set(names)) == len(names)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityService:
    """
    Checks whether every binding template and parameter definition
    referenced by a consumer projection execution capability registry
    event subscription lifecycle policy profile binding preset is
    mutually compatible, by evaluating a fixed set of named
    compatibility rules before a preset is instantiated or deployed.

    The service's responsibility is compatibility evaluation, not
    preset creation, registration, resolution, or persistence. It
    does NOT create presets, register binding templates, mutate a
    registry, persist results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it was
      constructed with
    - Deterministic: Same preset, member binding templates, parameter
      definitions, and rules always produce the same outcome,
      evaluated in a fixed, declared order
    - Side-effect free: Never mutates its inputs or the registries it
      checks against
    """

    _RULE_EVALUATORS = {
        "non_empty_members": _non_empty_members,
        "unique_template_targets": _unique_template_targets,
        "unique_parameter_names": _unique_parameter_names,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule(
            rule_id="non_empty_members",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule(
            rule_id="unique_template_targets",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule(
            rule_id="unique_parameter_names",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.WARNING,
        ),
    )

    def __init__(
        self,
        preset_resolver,
        template_registry,
        parameterization_service,
        rules=None,
    ):
        """
        Args:
            preset_resolver: The resolver used to resolve a preset and
                its eligible member binding templates for a preset ID.
                Any object exposing `resolve(preset_id)`, returning a
                result carrying `resolved`, `preset`, and `templates`,
                is accepted
            template_registry: The registry used to resolve a raw
                preset's member binding templates by ID. Any object
                exposing `find(template_id)` is accepted
            parameterization_service: The service used to look up a
                preset's declared parameters. Any object exposing
                `supported_parameters(preset_id)` is accepted
            rules: The compatibility rules to evaluate, or None to use
                the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
                has a blank or unrecognized rule ID, an invalid
                severity, or two rules share the same rule ID
        """

        self._preset_resolver = preset_resolver
        self._template_registry = template_registry
        self._parameterization_service = parameterization_service
        self._rules = self._validated_rules(rules if rules is not None else self.DEFAULT_RULES)

    def check(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a preset's
        eligible member binding templates and declared parameters.

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the preset is overall compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        self._validate_identifier(preset_id, "preset ID")

        result = self._preset_resolver.resolve(preset_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                f"Cannot check compatibility: no preset is registered under preset ID {preset_id!r}."
            )

        parameters = tuple(self._parameterization_service.supported_parameters(preset_id))

        return self._evaluate(result.templates, parameters)

    def supports(self, preset_id: str) -> bool:
        """
        Check whether a preset's eligible member binding templates and
        declared parameters are mutually compatible.

        Returns:
            True if every ERROR-severity compatibility rule passed,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        return self.check(preset_id).compatible

    def validate(self, preset) -> None:
        """
        Validate that a preset's member binding templates and
        declared parameters are compatible, raising if they are not.

        Member binding templates that are unknown to the configured
        template registry are skipped rather than treated as a
        failure.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError:
                If the preset is None, its preset ID is None or blank,
                or the preset fails a required compatibility rule
        """

        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                "Cannot validate a None preset."
            )

        preset_id = getattr(preset, "preset_id", None)

        self._validate_identifier(preset_id, "preset ID")

        templates = tuple(
            template
            for template in (self._template_registry.find(template_id) for template_id in preset.binding_template_ids)
            if template is not None
        )

        parameters = tuple(self._parameterization_service.supported_parameters(preset_id))

        result = self._evaluate(templates, parameters)

        if not result.compatible:
            rule_ids = ", ".join(violation.rule_id for violation in result.violations)

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                f"Preset failed required compatibility rules: {rule_ids}."
            )

    def rules(self) -> tuple:
        """
        List every configured compatibility rule, in evaluation
        order.
        """

        return self._rules

    def _evaluate(
        self,
        templates,
        parameters,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult:
        violations = []
        compatible = True

        for rule in self._rules:
            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(templates, parameters):
                violations.append(rule)

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity.ERROR:
                    compatible = False

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult(
            compatible=compatible,
            violations=tuple(violations),
        )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                f"Cannot check compatibility with an empty or blank {label}."
            )

    def _validated_rules(self, rules) -> tuple:
        seen_ids = set()
        validated = []

        for rule in rules:
            if rule is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                    "Cannot build a compatibility service with a None rule."
                )

            if not isinstance(
                rule,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                    "Cannot build a compatibility service: rule must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule."
                )

            if rule.rule_id is None or not rule.rule_id.strip() or rule.rule_id not in self._RULE_EVALUATORS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                    f"Cannot build a compatibility service with an invalid compatibility rule ID {rule.rule_id!r}."
                )

            if not isinstance(
                rule.severity,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                    f"Cannot build a compatibility service with a rule that has an unknown severity {rule.severity!r}."
                )

            if rule.rule_id in seen_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityError(
                    f"Cannot build a compatibility service with duplicate rule ID {rule.rule_id!r}."
                )

            seen_ids.add(rule.rule_id)
            validated.append(rule)

        return tuple(validated)
