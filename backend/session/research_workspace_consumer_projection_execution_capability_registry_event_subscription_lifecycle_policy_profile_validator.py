from collections import (
    Counter,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator:
    """
    Validates consumer projection execution capability registry
    event subscription lifecycle policy profiles, versions, and
    version histories before publication or activation.

    The validator's responsibility is checking and reporting, not
    registration, publication, or repair. It does NOT register
    profiles, publish versions, mutate its inputs, raise on invalid
    input, persist results, log, or publish events.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same input always produces the same result
    - Side-effect free: Never mutates its inputs
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def validate(

        self,

        profile,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult:
        """
        Validate a lifecycle policy profile.

        Args:
            profile: The profile to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the profile is valid
        """

        violations = []

        if profile is None:

            violations.append(
                self._violation(
                    "MISSING_PROFILE",

                    "Profile must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        profile_id = getattr(
            profile,
            "profile_id",
            None,
        )

        if profile_id is None or not profile_id.strip():

            violations.append(
                self._violation(
                    "MISSING_PROFILE_ID",

                    "Profile must have a non-blank profile ID.",

                    profile_id,
                )
            )

        profile_name = getattr(
            profile,
            "profile_name",
            None,
        )

        if profile_name is None or not profile_name.strip():

            violations.append(
                self._violation(
                    "MISSING_PROFILE_NAME",

                    "Profile must have a non-blank profile name.",

                    profile_id,
                )
            )

        policy_identifiers = getattr(
            profile,
            "policy_identifiers",
            None,
        ) or ()

        occurrences = Counter(
            policy_identifiers
        )

        for policy_identifier, count in occurrences.items():

            if count > 1:

                violations.append(
                    self._violation(
                        "DUPLICATE_POLICY_IDENTIFIER",

                        f"Policy identifier {policy_identifier!r} appears "
                        f"{count} times; policy identifiers must be "
                        "unique within a profile.",

                        profile_id,
                    )
                )

        return self._result(
            violations
        )

    def validate_version(

        self,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult:
        """
        Validate a lifecycle policy profile version.

        Args:
            version: The version to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the version is valid
        """

        violations = []

        if version is None:

            violations.append(
                self._violation(
                    "MISSING_VERSION",

                    "Version must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        version_identifier = getattr(
            version,
            "version",
            None,
        )

        if version_identifier is None or not version_identifier.strip():

            violations.append(
                self._violation(
                    "MISSING_VERSION_IDENTIFIER",

                    "Version must have a non-blank version identifier.",

                    None,
                )
            )

        if getattr(version, "policy_identifiers", None) is None:

            violations.append(
                self._violation(
                    "MISSING_POLICY_IDENTIFIERS",

                    "Version must have a policy identifier collection.",

                    None,
                )
            )

        return self._result(
            violations
        )

    def validate_history(

        self,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult:
        """
        Validate a lifecycle policy profile version history.

        Args:
            history: The version history to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the history is valid
        """

        violations = []

        if history is None:

            violations.append(
                self._violation(
                    "MISSING_HISTORY",

                    "Version history must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        profile_id = getattr(
            history,
            "profile_id",
            None,
        )

        if profile_id is None or not profile_id.strip():

            violations.append(
                self._violation(
                    "MISSING_PROFILE_ID",

                    "Version history must have a non-blank profile ID.",

                    profile_id,
                )
            )

        versions = getattr(
            history,
            "versions",
            None,
        ) or ()

        current_version = getattr(
            history,
            "current_version",
            None,
        )

        if current_version is None or not current_version.strip():

            violations.append(
                self._violation(
                    "MISSING_CURRENT_VERSION",

                    "Version history must have a non-blank current "
                    "version.",

                    profile_id,
                )
            )

        elif current_version not in {

            published.version

            for published

            in versions
        }:

            violations.append(
                self._violation(
                    "CURRENT_VERSION_NOT_IN_HISTORY",

                    f"Current version {current_version!r} was not found "
                    "among the history's published versions.",

                    profile_id,
                )
            )

        occurrences = Counter(
            published.version

            for published

            in versions
        )

        for version_identifier, count in occurrences.items():

            if count > 1:

                violations.append(
                    self._violation(
                        "DUPLICATE_VERSION",

                        f"Version {version_identifier!r} appears "
                        f"{count} times; version identifiers must be "
                        "unique within a profile's history.",

                        profile_id,
                    )
                )

        return self._result(
            violations
        )

    def _violation(

        self,

        code,

        message,

        profile_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationViolation:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationViolation(
                code=code,

                message=message,

                profile_id=profile_id,
            )
        )

    def _result(

        self,

        violations,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult(
                valid=len(violations) == 0,

                violations=tuple(
                    violations
                ),
            )
        )
