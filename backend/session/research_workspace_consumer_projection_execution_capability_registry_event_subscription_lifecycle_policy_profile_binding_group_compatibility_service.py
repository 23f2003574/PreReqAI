from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity,
)


def _non_empty_members(bindings) -> bool:
    return len(bindings) > 0


def _unique_capability_targets(bindings) -> bool:
    capability_ids = [binding.capability_id for binding in bindings]

    return len(set(capability_ids)) == len(capability_ids)


def _unique_profile_bindings(bindings) -> bool:
    profile_ids = [binding.profile_id for binding in bindings]

    return len(set(profile_ids)) == len(profile_ids)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityService:
    """
    Checks whether every binding grouped by a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding group is mutually compatible, by evaluating a
    fixed set of named compatibility rules before a group is deployed
    or activated.

    The service's responsibility is compatibility evaluation, not
    group creation, registration, resolution, or persistence. It does
    NOT create groups, register bindings, mutate a registry, persist
    results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it was
      constructed with
    - Deterministic: Same group, member bindings, and rules always
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
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule(
            rule_id="non_empty_members",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule(
            rule_id="unique_capability_targets",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule(
            rule_id="unique_profile_bindings",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.WARNING,
        ),
    )

    def __init__(
        self,
        group_resolver,
        binding_registry,
        rules=None,
    ):
        """
        Args:
            group_resolver: The resolver used to resolve a group and
                its eligible member bindings for a group ID. Any
                object exposing `resolve(group_id)`, returning a
                result carrying `resolved`, `group`, and `bindings`,
                is accepted
            binding_registry: The registry used to resolve a raw
                group's member bindings by ID. Any object exposing
                `find(binding_id)` is accepted
            rules: The compatibility rules to evaluate, or None to use
                the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule,
                has a blank or unrecognized rule ID, an invalid
                severity, or two rules share the same rule ID
        """

        self._group_resolver = group_resolver
        self._binding_registry = binding_registry
        self._rules = self._validated_rules(rules if rules is not None else self.DEFAULT_RULES)

    def check(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a group's
        eligible member bindings.

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the group is overall compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        self._validate_identifier(group_id, "group ID")

        result = self._group_resolver.resolve(group_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                f"Cannot check compatibility: no group is registered under group ID {group_id!r}."
            )

        return self._evaluate(result.bindings)

    def supports(self, group_id: str) -> bool:
        """
        Check whether a group's eligible member bindings are mutually
        compatible.

        Returns:
            True if every ERROR-severity compatibility rule passed,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        return self.check(group_id).compatible

    def validate(self, group) -> None:
        """
        Validate that a group's member bindings are compatible,
        raising if they are not.

        Member bindings that are unknown to the configured binding
        registry are skipped rather than treated as a failure.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError:
                If the group is None, its group ID is None or blank,
                or the group fails a required compatibility rule
        """

        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                "Cannot validate a None group."
            )

        self._validate_identifier(getattr(group, "group_id", None), "group ID")

        bindings = tuple(
            binding
            for binding in (self._binding_registry.find(binding_id) for binding_id in group.binding_ids)
            if binding is not None
        )

        result = self._evaluate(bindings)

        if not result.compatible:
            rule_ids = ", ".join(violation.rule_id for violation in result.violations)

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                f"Group failed required compatibility rules: {rule_ids}."
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
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult:
        violations = []
        compatible = True

        for rule in self._rules:
            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(bindings):
                violations.append(rule)

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity.ERROR:
                    compatible = False

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityResult(
            compatible=compatible,
            violations=tuple(violations),
        )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                f"Cannot check compatibility with an empty or blank {label}."
            )

    def _validated_rules(self, rules) -> tuple:
        seen_ids = set()
        validated = []

        for rule in rules:
            if rule is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                    "Cannot build a compatibility service with a None rule."
                )

            if not isinstance(
                rule,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                    "Cannot build a compatibility service: rule must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityRule."
                )

            if rule.rule_id is None or not rule.rule_id.strip() or rule.rule_id not in self._RULE_EVALUATORS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                    f"Cannot build a compatibility service with an invalid compatibility rule ID {rule.rule_id!r}."
                )

            if not isinstance(
                rule.severity,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                    f"Cannot build a compatibility service with a rule that has an unknown severity {rule.severity!r}."
                )

            if rule.rule_id in seen_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilityError(
                    f"Cannot build a compatibility service with duplicate rule ID {rule.rule_id!r}."
                )

            seen_ids.add(rule.rule_id)
            validated.append(rule)

        return tuple(validated)
