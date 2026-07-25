from collections import (
    Counter,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator:
    """
    Validates consumer projection execution capability registry
    event subscription lifecycle policy templates, versions, and
    version histories before publication or instantiation.

    The validator's responsibility is checking and reporting, not
    registration, publication, or repair. It does NOT register
    templates, publish versions, mutate its inputs, raise on
    invalid input, persist results, log, or publish events.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same input always produces the same result
    - Side-effect free: Never mutates its inputs
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def validate(

        self,

        template,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult:
        """
        Validate a lifecycle policy template.

        Args:
            template: The template to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the template is valid
        """

        violations = []

        if template is None:

            violations.append(
                self._violation(
                    "MISSING_TEMPLATE",

                    "Template must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        template_id = getattr(
            template,
            "template_id",
            None,
        )

        if template_id is None or not template_id.strip():

            violations.append(
                self._violation(
                    "MISSING_TEMPLATE_ID",

                    "Template must have a non-blank template ID.",

                    template_id,
                )
            )

        template_name = getattr(
            template,
            "template_name",
            None,
        )

        if template_name is None or not template_name.strip():

            violations.append(
                self._violation(
                    "MISSING_TEMPLATE_NAME",

                    "Template must have a non-blank template name.",

                    template_id,
                )
            )

        if getattr(template, "lifecycle_policy", None) is None:

            violations.append(
                self._violation(
                    "MISSING_LIFECYCLE_POLICY",

                    "Template must have a lifecycle policy.",

                    template_id,
                )
            )

        return self._result(
            violations
        )

    def validate_version(

        self,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult:
        """
        Validate a lifecycle policy template version.

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

        if getattr(version, "lifecycle_policy", None) is None:

            violations.append(
                self._violation(
                    "MISSING_LIFECYCLE_POLICY",

                    "Version must have a lifecycle policy.",

                    None,
                )
            )

        return self._result(
            violations
        )

    def validate_history(

        self,

        history,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult:
        """
        Validate a lifecycle policy template version history.

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

        template_id = getattr(
            history,
            "template_id",
            None,
        )

        if template_id is None or not template_id.strip():

            violations.append(
                self._violation(
                    "MISSING_TEMPLATE_ID",

                    "Version history must have a non-blank template ID.",

                    template_id,
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

                    template_id,
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

                    template_id,
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
                        "unique within a template's history.",

                        template_id,
                    )
                )

        return self._result(
            violations
        )

    def _violation(

        self,

        code,

        message,

        template_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationViolation:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationViolation(
                code=code,

                message=message,

                template_id=template_id,
            )
        )

    def _result(

        self,

        violations,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult(
                valid=len(violations) == 0,

                violations=tuple(
                    violations
                ),
            )
        )
