from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


def _non_empty_policy_identifiers(policy_identifiers) -> bool:

    return len(policy_identifiers) > 0


def _unique_policy_identifiers(policy_identifiers) -> bool:

    return len(
        set(
            policy_identifiers
        )
    ) == len(
        policy_identifiers
    )


def _no_blank_policy_identifiers(policy_identifiers) -> bool:

    return all(

        identifier is not None and identifier.strip()

        for identifier

        in policy_identifiers
    )


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService:
    """
    Checks whether a consumer projection execution capability
    registry event subscription lifecycle policy profile can safely
    coexist with registry capabilities, deployment targets, and
    profile versions, by evaluating a fixed set of named
    compatibility rules.

    The service's responsibility is compatibility evaluation, not
    profile registration, resolution, validation of the profile's
    own fields, or instantiation. It does NOT register profiles,
    mutate a registry or version history, instantiate profiles,
    persist results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it
      was constructed with
    - Deterministic: Same profile, version, and rules always produce
      the same outcome, evaluated in a fixed, declared order
    - Side-effect free: Never mutates its inputs, the registry, or
      the version history it checks against
    """

    _RULE_EVALUATORS = {

        "non_empty_policy_identifiers": _non_empty_policy_identifiers,

        "unique_policy_identifiers": _unique_policy_identifiers,

        "no_blank_policy_identifiers": _no_blank_policy_identifiers,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
            rule_id="non_empty_policy_identifiers",

            description="Profile must group at least one policy identifier.",

            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
            rule_id="unique_policy_identifiers",

            description="Profile must not group duplicate policy identifiers.",

            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule(
            rule_id="no_blank_policy_identifiers",

            description="Profile must not group empty or blank policy identifiers.",

            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR,
        ),
    )

    def __init__(

        self,

        resolver,

        version_service,

        rules=None,

    ):
        """
        Args:
            resolver: The profile resolver used by check_version() to
                resolve a profile ID. Any object exposing
                `resolve_or_raise(profile_id)` is accepted
            version_service: The version service used by
                check_version() to resolve a profile's published
                versions. Any object exposing
                `find(profile_id, version)` is accepted
            rules: The compatibility rules to evaluate, or None to
                use the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
                has a blank or unrecognized rule ID, a blank
                description, an invalid severity, or two rules share
                the same rule ID
        """

        self._resolver = resolver

        self._version_service = version_service

        self._rules = self._validated_rules(

            rules

            if rules is not None

            else self.DEFAULT_RULES
        )

    def check(

        self,

        profile,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a profile.

        Args:
            profile: The profile to check

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the profile is overall
            compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:
                If the profile is None or has a missing policy
                identifier collection
        """

        if profile is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    "Cannot check compatibility for a None profile."
                )
            )

        if profile.policy_identifiers is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    "Cannot check compatibility for a profile with a "
                    "missing policy identifier collection."
                )
            )

        return self._evaluate(
            profile.policy_identifiers
        )

    def check_version(

        self,

        profile_id,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a specific
        published version of a profile.

        Args:
            profile_id: The profile ID to check
            version: The version identifier to check

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the version is overall
            compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:
                If the profile ID or version is None or blank, the
                profile cannot be resolved, or no such version was
                published for the profile
        """

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        self._validate_identifier(
            version,

            "version",
        )

        try:

            self._resolver.resolve_or_raise(
                profile_id
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    "Cannot check compatibility: no profile was found "
                    f"under profile ID {profile_id!r}."
                )
            ) from error

        published_version = self._version_service.find(

            profile_id,

            version,
        )

        if published_version is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    f"Cannot check compatibility: version {version!r} was "
                    f"not found for profile ID {profile_id!r}."
                )
            )

        return self._evaluate(
            published_version.policy_identifiers
        )

    def supports(

        self,

        profile,

        capability,

    ) -> bool:
        """
        Check whether a profile declares support for a capability.

        Args:
            profile: The profile to check
            capability: The capability identifier to check for

        Returns:
            True if the capability is among the profile's grouped
            policy identifiers, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:
                If the profile is None, or the capability is None or
                blank
        """

        if profile is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    "Cannot check capability support for a None profile."
                )
            )

        self._validate_identifier(
            capability,

            "capability",
        )

        return capability in profile.policy_identifiers

    def validate(

        self,

        profile,

    ) -> None:
        """
        Validate that a profile is compatible, raising if it is not.

        Args:
            profile: The profile to validate

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:
                If the profile is None or has a missing policy
                identifier collection, or the profile fails a
                required compatibility rule
        """

        result = self.check(
            profile
        )

        if not result.compatible:

            descriptions = ", ".join(

                incompatibility.rule_id

                for incompatibility

                in result.incompatibilities
            )

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    "Profile failed required compatibility rules: "
                    f"{descriptions}."
                )
            )

    def _evaluate(

        self,

        policy_identifiers,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult:

        incompatibilities = []

        compatible = True

        for rule in self._rules:

            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(policy_identifiers):

                incompatibilities.append(
                    rule
                )

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity.ERROR:

                    compatible = False

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult(
                compatible=compatible,

                incompatibilities=tuple(
                    incompatibilities
                ),
            )
        )

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                    f"Cannot check compatibility with an empty or blank {label}."
                )
            )

    def _validated_rules(

        self,

        rules,

    ) -> tuple:

        seen_ids = set()

        validated = []

        for rule in rules:

            if rule is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service with a None "
                        "rule."
                    )
                )

            if not isinstance(

                rule,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service: rule must be "
                        "a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule."
                    )
                )

            if (

                rule.rule_id is None

                or not rule.rule_id.strip()

                or rule.rule_id not in self._RULE_EVALUATORS
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service with an "
                        f"invalid compatibility rule ID {rule.rule_id!r}."
                    )
                )

            if (

                rule.description is None

                or not rule.description.strip()
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service with a rule "
                        "that has an empty or blank description."
                    )
                )

            if not isinstance(

                rule.severity,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service with a rule "
                        f"that has an unknown severity {rule.severity!r}."
                    )
                )

            if rule.rule_id in seen_ids:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError(
                        "Cannot build a compatibility service with "
                        f"duplicate rule ID {rule.rule_id!r}."
                    )
                )

            seen_ids.add(
                rule.rule_id
            )

            validated.append(
                rule
            )

        return tuple(
            validated
        )
