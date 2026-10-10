from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile assignments, registries,
    and resolution results before registration or resolution.

    The validator's responsibility is checking and reporting, not
    registration, resolution, or repair. It does NOT register
    assignments, resolve targets, mutate its inputs, raise on invalid
    input, persist results, log, or publish events.

    The validator is:
    - Stateless: No mutable instance state; the profile registry it
      was constructed with is treated as read-only
    - Deterministic: Same input and registry state always produce the
      same result
    - Side-effect free: Never mutates its inputs or the registry
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def __init__(

        self,

        profile_registry,

    ):
        """
        Args:
            profile_registry: The profile registry used to verify
                that an assigned profile exists. Any object exposing
                a `contains(profile_id)` lookup is accepted
        """

        self._profile_registry = profile_registry

    def validate(

        self,

        assignment,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult:
        """
        Validate a single profile assignment.

        Checks that the assignment is not None, that its target and
        profile IDs are present and non-blank, and that the assigned
        profile exists in the configured profile registry.

        Args:
            assignment: The assignment to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the assignment is valid
        """

        violations = []

        if assignment is None:

            violations.append(
                self._violation(
                    "MISSING_ASSIGNMENT",

                    "Assignment must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        target_id = getattr(
            assignment,
            "target_id",
            None,
        )

        if target_id is None or not target_id.strip():

            violations.append(
                self._violation(
                    "MISSING_TARGET_ID",

                    "Assignment must have a non-blank target ID.",

                    target_id,
                )
            )

        profile_id = getattr(
            assignment,
            "profile_id",
            None,
        )

        if profile_id is None or not profile_id.strip():

            violations.append(
                self._violation(
                    "MISSING_PROFILE_ID",

                    "Assignment must have a non-blank profile ID.",

                    target_id,
                )
            )

        elif not self._profile_registry.contains(profile_id):

            violations.append(
                self._violation(
                    "UNKNOWN_PROFILE",

                    f"Profile ID {profile_id!r} is not registered in the "
                    "profile registry.",

                    target_id,
                )
            )

        return self._result(
            violations
        )

    def validate_registry(

        self,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult:
        """
        Validate an assignment registry for duplicate target IDs and
        individually invalid assignments.

        Args:
            registry: The registry to validate. Any object exposing
                an `assignments` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found, empty if the registry is valid
        """

        violations = []

        if registry is None:

            violations.append(
                self._violation(
                    "MISSING_REGISTRY",

                    "Registry must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        assignments = getattr(
            registry,
            "assignments",
            None,
        )

        if assignments is None:

            violations.append(
                self._violation(
                    "MISSING_ASSIGNMENTS",

                    "Registry must expose an assignments mapping.",

                    None,
                )
            )

            return self._result(
                violations
            )

        seen_target_ids = set()

        for target_id, assignment in assignments.items():

            if target_id in seen_target_ids:

                violations.append(
                    self._violation(
                        "DUPLICATE_TARGET_ID",

                        f"Target ID {target_id!r} appears more than once in "
                        "the registry; target IDs must be unique.",

                        target_id,
                    )
                )

            seen_target_ids.add(target_id)

            assignment_result = self.validate(
                assignment
            )

            for violation in assignment_result.violations:

                violations.append(
                    violation
                )

        return self._result(
            violations
        )

    def validate_resolution(

        self,

        result,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult:
        """
        Validate a resolution result produced by an assignment
        resolver.

        Checks that the result is not None, that a resolved result
        carries a valid assignment, and that an unresolved result
        carries neither an assignment nor a resolution source.

        Args:
            result: The resolution result to validate

        Returns:
            An immutable validation result carrying every violation
            found, empty if the resolution result is valid
        """

        violations = []

        if result is None:

            violations.append(
                self._violation(
                    "MISSING_RESOLUTION_RESULT",

                    "Resolution result must not be None.",

                    None,
                )
            )

            return self._result(
                violations
            )

        resolved = getattr(
            result,
            "resolved",
            None,
        )

        assignment = getattr(
            result,
            "assignment",
            None,
        )

        resolution_source = getattr(
            result,
            "resolution_source",
            None,
        )

        if resolved is True:

            if assignment is None:

                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_ASSIGNMENT",

                        "A resolved resolution result must carry an "
                        "assignment.",

                        None,
                    )
                )

            else:

                assignment_result = self.validate(
                    assignment
                )

                for violation in assignment_result.violations:

                    violations.append(
                        violation
                    )

            if resolution_source is None:

                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_SOURCE",

                        "A resolved resolution result must carry a "
                        "resolution source.",

                        None,
                    )
                )

        elif resolved is False:

            if assignment is not None:

                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_ASSIGNMENT",

                        "An unresolved resolution result must not carry an "
                        "assignment.",

                        None,
                    )
                )

            if resolution_source is not None:

                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_SOURCE",

                        "An unresolved resolution result must not carry a "
                        "resolution source.",

                        None,
                    )
                )

        else:

            violations.append(
                self._violation(
                    "INVALID_RESOLVED_FLAG",

                    "Resolution result must have a boolean resolved flag.",

                    None,
                )
            )

        return self._result(
            violations
        )

    def _violation(

        self,

        code,

        message,

        target_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationViolation:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationViolation(
                code=code,

                message=message,

                target_id=target_id,
            )
        )

    def _result(

        self,

        violations,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult:

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationResult(
                valid=len(violations) == 0,

                violations=tuple(
                    violations
                ),
            )
        )
