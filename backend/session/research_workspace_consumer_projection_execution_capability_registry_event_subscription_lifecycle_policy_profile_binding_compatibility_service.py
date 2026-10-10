from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity,
)


def _non_empty_policy_identifiers(policy_identifiers, capability_id) -> bool:
    return len(policy_identifiers) > 0


def _unique_policy_identifiers(policy_identifiers, capability_id) -> bool:
    return len(set(policy_identifiers)) == len(policy_identifiers)


def _no_blank_policy_identifiers(policy_identifiers, capability_id) -> bool:
    return all(identifier is not None and identifier.strip() for identifier in policy_identifiers)


def _capability_supported(policy_identifiers, capability_id) -> bool:
    return capability_id in policy_identifiers


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityService:
    """
    Checks whether a consumer projection execution capability
    registry event subscription lifecycle policy profile can safely
    be bound to an execution capability, by evaluating a fixed set of
    named compatibility rules before a binding is created or updated.

    The service's responsibility is compatibility evaluation, not
    binding creation, profile or capability registration, or
    persistence. It does NOT create bindings, register profiles or
    capabilities, mutate a registry, persist results, log, or publish
    events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it was
      constructed with
    - Deterministic: Same profile, capability, and rules always
      produce the same outcome, evaluated in a fixed, declared order
    - Side-effect free: Never mutates its inputs or the registries it
      checks against
    """

    _RULE_EVALUATORS = {
        "non_empty_policy_identifiers": _non_empty_policy_identifiers,
        "unique_policy_identifiers": _unique_policy_identifiers,
        "no_blank_policy_identifiers": _no_blank_policy_identifiers,
        "capability_supported": _capability_supported,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
            rule_id="non_empty_policy_identifiers",
            description="Profile must group at least one policy identifier.",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
            rule_id="unique_policy_identifiers",
            description="Profile must not group duplicate policy identifiers.",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
            rule_id="no_blank_policy_identifiers",
            description="Profile must not group empty or blank policy identifiers.",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule(
            rule_id="capability_supported",
            description="Profile must declare support for the capability among its policy identifiers.",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR,
        ),
    )

    def __init__(
        self,
        profile_registry,
        capability_registry,
        rules=None,
    ):
        """
        Args:
            profile_registry: The profile registry used to resolve a
                profile ID. Any object exposing `contains(profile_id)`
                and `find(profile_id)` is accepted
            capability_registry: The capability registry used to
                verify a capability exists. Any object exposing
                `contains(capability_id)` is accepted
            rules: The compatibility rules to evaluate, or None to use
                the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule,
                has a blank or unrecognized rule ID, a blank
                description, an invalid severity, or two rules share
                the same rule ID
        """

        self._profile_registry = profile_registry
        self._capability_registry = capability_registry
        self._rules = self._validated_rules(rules if rules is not None else self.DEFAULT_RULES)

    def check(
        self,
        profile_id: str,
        capability_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a
        profile-capability pairing.

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the pairing is overall compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError:
                If the profile ID or capability ID is None or blank,
                no profile is registered under the profile ID, or no
                capability is registered under the capability ID
        """

        profile = self._resolve_profile(profile_id)
        self._validate_capability(capability_id)

        return self._evaluate(profile.policy_identifiers, capability_id)

    def supports(
        self,
        profile_id: str,
        capability_id: str,
    ) -> bool:
        """
        Check whether a profile declares support for a capability.

        Returns:
            True if the capability is among the profile's grouped
            policy identifiers, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError:
                If the profile ID or capability ID is None or blank,
                no profile is registered under the profile ID, or no
                capability is registered under the capability ID
        """

        profile = self._resolve_profile(profile_id)
        self._validate_capability(capability_id)

        return capability_id in profile.policy_identifiers

    def validate(self, binding) -> None:
        """
        Validate that a binding is compatible, raising if it is not.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError:
                If the binding is None, its profile or capability ID
                is None or blank or unknown, or the binding fails a
                required compatibility rule
        """

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                "Cannot validate a None binding."
            )

        result = self.check(binding.profile_id, binding.capability_id)

        if not result.compatible:
            rule_ids = ", ".join(violation.rule_id for violation in result.violations)

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                f"Binding failed required compatibility rules: {rule_ids}."
            )

    def list_rules(self) -> tuple:
        """
        List every configured compatibility rule, in evaluation
        order.
        """

        return self._rules

    def _resolve_profile(self, profile_id: str):
        self._validate_identifier(profile_id, "profile ID")

        if not self._profile_registry.contains(profile_id):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                f"Cannot check compatibility: no profile is registered under profile ID {profile_id!r}."
            )

        return self._profile_registry.find(profile_id)

    def _validate_capability(self, capability_id: str) -> None:
        self._validate_identifier(capability_id, "capability ID")

        if not self._capability_registry.contains(capability_id):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                f"Cannot check compatibility: no capability is registered under capability ID {capability_id!r}."
            )

    def _evaluate(
        self,
        policy_identifiers,
        capability_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult:
        violations = []
        compatible = True

        for rule in self._rules:
            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(policy_identifiers, capability_id):
                violations.append(rule)

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity.ERROR:
                    compatible = False

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityResult(
            compatible=compatible,
            violations=tuple(violations),
        )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                f"Cannot check compatibility with an empty or blank {label}."
            )

    def _validated_rules(self, rules) -> tuple:
        seen_ids = set()
        validated = []

        for rule in rules:
            if rule is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    "Cannot build a compatibility service with a None rule."
                )

            if not isinstance(
                rule,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    "Cannot build a compatibility service: rule must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityRule."
                )

            if rule.rule_id is None or not rule.rule_id.strip() or rule.rule_id not in self._RULE_EVALUATORS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    f"Cannot build a compatibility service with an invalid compatibility rule ID {rule.rule_id!r}."
                )

            if rule.description is None or not rule.description.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    "Cannot build a compatibility service with a rule that has an empty or blank description."
                )

            if not isinstance(
                rule.severity,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilitySeverity,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    f"Cannot build a compatibility service with a rule that has an unknown severity {rule.severity!r}."
                )

            if rule.rule_id in seen_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCompatibilityError(
                    f"Cannot build a compatibility service with duplicate rule ID {rule.rule_id!r}."
                )

            seen_ids.add(rule.rule_id)
            validated.append(rule)

        return tuple(validated)
