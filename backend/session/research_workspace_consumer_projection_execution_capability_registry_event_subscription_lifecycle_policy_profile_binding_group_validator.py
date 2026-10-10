from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile binding groups, registries,
    and resolution results before registration or resolution,
    guaranteeing structural integrity.

    The validator's responsibility is checking and reporting, not
    registration, resolution, or repair. It does NOT register groups,
    resolve groups, mutate its inputs, raise on invalid input, persist
    results, log, or publish events.

    The validator is:
    - Stateless: No mutable instance state; the binding registry it
      was constructed with is treated as read-only
    - Deterministic: Same input and registry state always produce the
      same result
    - Side-effect free: Never mutates its inputs or the registries
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def __init__(self, binding_registry):
        """
        Args:
            binding_registry: The registry used to verify that a
                member binding exists. Any object exposing a
                `contains(binding_id)` lookup is accepted
        """

        self._binding_registry = binding_registry

    def validate(
        self,
        group,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult:
        """
        Validate a single binding group.

        Checks that the group is not None, that its group ID and name
        are present and non-blank, that its member bindings are
        unique, and that every member binding exists in the configured
        binding registry.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the group is valid
        """

        violations = []

        if group is None:
            violations.append(
                self._violation("MISSING_GROUP", "Group must not be None.", None)
            )

            return self._result(violations)

        group_id = getattr(group, "group_id", None)

        if group_id is None or not group_id.strip():
            violations.append(
                self._violation("MISSING_GROUP_ID", "Group must have a non-blank group ID.", group_id)
            )

        group_name = getattr(group, "group_name", None)

        if group_name is None or not group_name.strip():
            violations.append(
                self._violation("MISSING_GROUP_NAME", "Group must have a non-blank group name.", group_id)
            )

        binding_ids = getattr(group, "binding_ids", None)

        if binding_ids is None:
            violations.append(
                self._violation("MISSING_BINDING_IDS", "Group must expose a binding_ids collection.", group_id)
            )
        else:
            seen_binding_ids = set()

            for binding_id in binding_ids:
                if binding_id is None or not str(binding_id).strip():
                    violations.append(
                        self._violation(
                            "MISSING_MEMBER_BINDING_ID",
                            "Group member binding ID must be non-blank.",
                            group_id,
                        )
                    )

                    continue

                if binding_id in seen_binding_ids:
                    violations.append(
                        self._violation(
                            "DUPLICATE_MEMBER",
                            f"Binding ID {binding_id!r} is a member of the group more than once; "
                            "group members must be unique.",
                            group_id,
                        )
                    )

                seen_binding_ids.add(binding_id)

                if not self._binding_registry.contains(binding_id):
                    violations.append(
                        self._violation(
                            "UNKNOWN_BINDING",
                            f"Binding ID {binding_id!r} is not registered in the binding registry.",
                            group_id,
                        )
                    )

        return self._result(violations)

    def validate_registry(
        self,
        registry,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult:
        """
        Validate every group registered in a binding group registry.

        Args:
            registry: The registry to validate. Any object exposing
                a `groups` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found across every registered group, empty if the
            registry is valid
        """

        violations = []

        if registry is None:
            violations.append(
                self._violation("MISSING_REGISTRY", "Registry must not be None.", None)
            )

            return self._result(violations)

        groups = getattr(registry, "groups", None)

        if groups is None:
            violations.append(
                self._violation("MISSING_GROUPS", "Registry must expose a groups mapping.", None)
            )

            return self._result(violations)

        for group in groups.values():
            group_result = self.validate(group)

            for violation in group_result.violations:
                violations.append(violation)

        return self._result(violations)

    def validate_resolution(
        self,
        result,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult:
        """
        Validate a resolution result produced by a binding group
        resolver.

        Checks that the result is not None, that a resolved result
        carries a valid group and a resolution source, and that an
        unresolved result carries neither a group, member bindings,
        nor a resolution source.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the resolution result is valid
        """

        violations = []

        if result is None:
            violations.append(
                self._violation("MISSING_RESOLUTION_RESULT", "Resolution result must not be None.", None)
            )

            return self._result(violations)

        resolved = getattr(result, "resolved", None)
        group = getattr(result, "group", None)
        bindings = getattr(result, "bindings", None)
        source = getattr(result, "source", None)

        if resolved is True:
            if group is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_GROUP",
                        "A resolved resolution result must carry a group.",
                        None,
                    )
                )
            else:
                group_result = self.validate(group)

                for violation in group_result.violations:
                    violations.append(violation)

            if source is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_SOURCE",
                        "A resolved resolution result must carry a resolution source.",
                        getattr(group, "group_id", None),
                    )
                )

        elif resolved is False:
            if group is not None:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_GROUP",
                        "An unresolved resolution result must not carry a group.",
                        None,
                    )
                )

            if bindings:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_BINDINGS",
                        "An unresolved resolution result must not carry member bindings.",
                        None,
                    )
                )

            if source is not None:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_SOURCE",
                        "An unresolved resolution result must not carry a resolution source.",
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

        return self._result(violations)

    def _violation(
        self,
        code,
        message,
        group_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationViolation:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationViolation(
            code=code,
            message=message,
            group_id=group_id,
        )

    def _result(
        self,
        violations,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult(
            valid=len(violations) == 0,
            violations=tuple(violations),
        )
