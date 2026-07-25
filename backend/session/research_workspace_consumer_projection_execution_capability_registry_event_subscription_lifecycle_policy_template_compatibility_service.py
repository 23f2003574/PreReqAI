from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule,
)


def _allowed_states_superset(template, lifecycle_policy) -> bool:

    return set(
        lifecycle_policy.allowed_states
    ).issubset(
        set(
            template.lifecycle_policy.allowed_states
        )
    )


def _initial_state_supported(template, lifecycle_policy) -> bool:

    return (
        lifecycle_policy.initial_state
        in template.lifecycle_policy.allowed_states
    )


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService:
    """
    Checks whether a consumer projection execution capability
    registry event subscription lifecycle policy template can
    safely instantiate or replace an existing lifecycle policy, by
    evaluating a fixed set of named compatibility rules.

    The service's responsibility is compatibility evaluation, not
    template registration, resolution, validation of the template's
    own fields, or instantiation. It does NOT register templates,
    resolve templates, instantiate policies, persist results, log,
    or publish events.

    The service is:
    - Stateless: Holds only the fixed rules it was constructed with
    - Deterministic: Same template, lifecycle policy, and rules
      always produce the same outcome
    - Side-effect free: Never mutates its inputs
    """

    _RULE_EVALUATORS = {

        "allowed_states_superset": _allowed_states_superset,

        "initial_state_supported": _initial_state_supported,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule(
            rule_name="allowed_states_superset",

            required=True,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule(
            rule_name="initial_state_supported",

            required=True,
        ),
    )

    def __init__(

        self,

        rules=None,

    ):
        """
        Args:
            rules: The compatibility rules to evaluate, or None to
                use the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule,
                has a blank or unrecognized rule name, or two rules
                share the same rule name
        """

        self._rules = self._validated_rules(

            rules

            if rules is not None

            else self.DEFAULT_RULES
        )

    def check(

        self,

        template,

        lifecycle_policy,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a template
        against an existing lifecycle policy.

        Args:
            template: The template to check
            lifecycle_policy: The existing lifecycle policy the
                template would instantiate or replace

        Returns:
            An immutable compatibility result carrying every rule
            name that failed and whether the template is overall
            compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError:
                If the template, its lifecycle policy, or the
                existing lifecycle policy is None
        """

        self._validate_inputs(

            template,

            lifecycle_policy,
        )

        incompatible_fields = []

        compatible = True

        for rule in self._rules:

            evaluator = self._RULE_EVALUATORS[rule.rule_name]

            if not evaluator(template, lifecycle_policy):

                incompatible_fields.append(
                    rule.rule_name
                )

                if rule.required:

                    compatible = False

        reason = (
            "Template failed required compatibility rules: "
            f"{', '.join(incompatible_fields)}."
            if not compatible
            else None
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult(
                compatible=compatible,

                incompatible_fields=tuple(
                    incompatible_fields
                ),

                reason=reason,
            )
        )

    def validate(

        self,

        template,

        lifecycle_policy,

    ) -> None:
        """
        Validate that a template is compatible with an existing
        lifecycle policy, raising if it is not.

        Args:
            template: The template to validate
            lifecycle_policy: The existing lifecycle policy the
                template would instantiate or replace

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError:
                If the template, its lifecycle policy, or the
                existing lifecycle policy is None, or the template
                fails a required compatibility rule
        """

        result = self.check(

            template,

            lifecycle_policy,
        )

        if not result.compatible:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                    result.reason
                )
            )

    def supports(

        self,

        template,

        lifecycle_policy,

    ) -> bool:
        """
        Check whether a template is compatible with an existing
        lifecycle policy.

        Args:
            template: The template to check
            lifecycle_policy: The existing lifecycle policy the
                template would instantiate or replace

        Returns:
            True if the template is compatible, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError:
                If the template, its lifecycle policy, or the
                existing lifecycle policy is None
        """

        return self.check(

            template,

            lifecycle_policy,
        ).compatible

    def _validate_inputs(

        self,

        template,

        lifecycle_policy,

    ) -> None:

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                    "Cannot check compatibility for a None template."
                )
            )

        if template.lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                    "Cannot check compatibility for a template with a "
                    "missing lifecycle policy."
                )
            )

        if lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                    "Cannot check compatibility against a None lifecycle "
                    "policy."
                )
            )

    def _validated_rules(

        self,

        rules,

    ) -> tuple:

        seen_names = set()

        validated = []

        for rule in rules:

            if rule is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                        "Cannot build a compatibility service with a None "
                        "rule."
                    )
                )

            if not isinstance(

                rule,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                        "Cannot build a compatibility service: rule must be "
                        "a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule."
                    )
                )

            if (

                rule.rule_name is None

                or not rule.rule_name.strip()

                or rule.rule_name not in self._RULE_EVALUATORS
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                        "Cannot build a compatibility service with an "
                        f"invalid compatibility rule name {rule.rule_name!r}."
                    )
                )

            if rule.rule_name in seen_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError(
                        "Cannot build a compatibility service with "
                        f"duplicate rule name {rule.rule_name!r}."
                    )
                )

            seen_names.add(
                rule.rule_name
            )

            validated.append(
                rule
            )

        return tuple(
            validated
        )
