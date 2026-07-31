from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity,
)


def _non_empty_members(bindings) -> bool:
    return len(bindings) > 0


def _unique_capability_targets(bindings) -> bool:
    capability_ids = [binding.capability_id for binding in bindings]

    return len(set(capability_ids)) == len(capability_ids)


def _unique_profile_bindings(bindings) -> bool:
    profile_ids = [binding.profile_id for binding in bindings]

    return len(set(profile_ids)) == len(profile_ids)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityService:
    """
    Checks whether every binding referenced by a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding template is mutually compatible, by evaluating a
    fixed set of named compatibility rules before a template is
    instantiated or deployed.

    The service's responsibility is compatibility evaluation, not
    template creation, registration, resolution, or persistence. It
    does NOT create templates, register bindings, mutate a registry,
    persist results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it was
      constructed with
    - Deterministic: Same template, member bindings, and rules always
      produce the same outcome, evaluated in a fixed, declared order
    - Side-effect free: Never mutates its inputs or the registries it
      checks against
    """

    _RULE_EVALUATORS = {
        "non_empty_members": _non_empty_members,
        "unique_capability_targets": _unique_capability_targets,
        "unique_profile_bindings": _unique_profile_bindings,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule(
            rule_id="non_empty_members",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule(
            rule_id="unique_capability_targets",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule(
            rule_id="unique_profile_bindings",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.WARNING,
        ),
    )

    def __init__(
        self,
        template_resolver,
        binding_registry,
        rules=None,
    ):
        """
        Args:
            template_resolver: The resolver used to resolve a
                template and its eligible member bindings for a
                template ID. Any object exposing `resolve(template_id)`,
                returning a result carrying `resolved`, `template`,
                and `bindings`, is accepted
            binding_registry: The registry used to resolve a raw
                template's member bindings by ID. Any object exposing
                `find(binding_id)` is accepted
            rules: The compatibility rules to evaluate, or None to use
                the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule,
                has a blank or unrecognized rule ID, an invalid
                severity, or two rules share the same rule ID
        """

        self._template_resolver = template_resolver
        self._binding_registry = binding_registry
        self._rules = self._validated_rules(rules if rules is not None else self.DEFAULT_RULES)

    def check(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a template's
        eligible member bindings.

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the template is overall
            compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError:
                If the template ID is None or blank, or no template
                is registered under it
        """

        self._validate_identifier(template_id, "template ID")

        result = self._template_resolver.resolve(template_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                f"Cannot check compatibility: no template is registered under template ID {template_id!r}."
            )

        return self._evaluate(result.bindings)

    def supports(self, template_id: str) -> bool:
        """
        Check whether a template's eligible member bindings are
        mutually compatible.

        Returns:
            True if every ERROR-severity compatibility rule passed,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError:
                If the template ID is None or blank, or no template
                is registered under it
        """

        return self.check(template_id).compatible

    def validate(self, template) -> None:
        """
        Validate that a template's member bindings are compatible,
        raising if they are not.

        Member bindings that are unknown to the configured binding
        registry are skipped rather than treated as a failure.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError:
                If the template is None, its template ID is None or
                blank, or the template fails a required compatibility
                rule
        """

        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                "Cannot validate a None template."
            )

        self._validate_identifier(getattr(template, "template_id", None), "template ID")

        bindings = tuple(
            binding
            for binding in (self._binding_registry.find(binding_id) for binding_id in template.binding_ids)
            if binding is not None
        )

        result = self._evaluate(bindings)

        if not result.compatible:
            rule_ids = ", ".join(violation.rule_id for violation in result.violations)

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                f"Template failed required compatibility rules: {rule_ids}."
            )

    def rules(self) -> tuple:
        """
        List every configured compatibility rule, in evaluation
        order.
        """

        return self._rules

    def _evaluate(
        self,
        bindings,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult:
        violations = []
        compatible = True

        for rule in self._rules:
            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(bindings):
                violations.append(rule)

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity.ERROR:
                    compatible = False

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityResult(
            compatible=compatible,
            violations=tuple(violations),
        )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                f"Cannot check compatibility with an empty or blank {label}."
            )

    def _validated_rules(self, rules) -> tuple:
        seen_ids = set()
        validated = []

        for rule in rules:
            if rule is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                    "Cannot build a compatibility service with a None rule."
                )

            if not isinstance(
                rule,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                    "Cannot build a compatibility service: rule must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityRule."
                )

            if rule.rule_id is None or not rule.rule_id.strip() or rule.rule_id not in self._RULE_EVALUATORS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                    f"Cannot build a compatibility service with an invalid compatibility rule ID {rule.rule_id!r}."
                )

            if not isinstance(
                rule.severity,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilitySeverity,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                    f"Cannot build a compatibility service with a rule that has an unknown severity {rule.severity!r}."
                )

            if rule.rule_id in seen_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCompatibilityError(
                    f"Cannot build a compatibility service with duplicate rule ID {rule.rule_id!r}."
                )

            seen_ids.add(rule.rule_id)
            validated.append(rule)

        return tuple(validated)
