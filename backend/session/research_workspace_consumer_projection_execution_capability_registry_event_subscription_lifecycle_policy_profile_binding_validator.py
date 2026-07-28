from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile bindings, registries, and
    resolution results before registration or resolution, guaranteeing
    registry consistency.

    The validator's responsibility is checking and reporting, not
    registration, resolution, or repair. It does NOT register
    bindings, resolve capabilities, mutate its inputs, raise on
    invalid input, persist results, log, or publish events.

    The validator is:
    - Stateless: No mutable instance state; the profile and
      capability registries it was constructed with are treated as
      read-only
    - Deterministic: Same input and registry state always produce the
      same result
    - Side-effect free: Never mutates its inputs or the registries
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def __init__(
        self,
        profile_registry,
        capability_registry,
    ):
        """
        Args:
            profile_registry: The profile registry used to verify
                that a bound profile exists. Any object exposing a
                `contains(profile_id)` lookup is accepted
            capability_registry: The capability registry used to
                verify that a bound capability exists. Any object
                exposing a `contains(capability_id)` lookup is
                accepted
        """

        self._profile_registry = profile_registry
        self._capability_registry = capability_registry

    def validate(
        self,
        binding,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult:
        """
        Validate a single profile binding.

        Checks that the binding is not None, that its profile and
        capability IDs are present and non-blank, and that the bound
        profile and capability exist in their configured registries.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the binding is valid
        """

        violations = []

        if binding is None:
            violations.append(
                self._violation("MISSING_BINDING", "Binding must not be None.", None)
            )

            return self._result(violations)

        binding_id = getattr(binding, "binding_id", None)

        if binding_id is None or not binding_id.strip():
            violations.append(
                self._violation("MISSING_BINDING_ID", "Binding must have a non-blank binding ID.", binding_id)
            )

        profile_id = getattr(binding, "profile_id", None)

        if profile_id is None or not profile_id.strip():
            violations.append(
                self._violation("MISSING_PROFILE_ID", "Binding must have a non-blank profile ID.", binding_id)
            )
        elif not self._profile_registry.contains(profile_id):
            violations.append(
                self._violation(
                    "UNKNOWN_PROFILE",
                    f"Profile ID {profile_id!r} is not registered in the profile registry.",
                    binding_id,
                )
            )

        capability_id = getattr(binding, "capability_id", None)

        if capability_id is None or not capability_id.strip():
            violations.append(
                self._violation("MISSING_CAPABILITY_ID", "Binding must have a non-blank capability ID.", binding_id)
            )
        elif not self._capability_registry.contains(capability_id):
            violations.append(
                self._violation(
                    "UNKNOWN_CAPABILITY",
                    f"Capability ID {capability_id!r} is not registered in the capability registry.",
                    binding_id,
                )
            )

        return self._result(violations)

    def validate_registry(
        self,
        registry,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult:
        """
        Validate a binding registry for duplicate (profile_id,
        capability_id) pairs and individually invalid bindings.

        Args:
            registry: The registry to validate. Any object exposing
                a `bindings` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found, empty if the registry is valid
        """

        violations = []

        if registry is None:
            violations.append(
                self._violation("MISSING_REGISTRY", "Registry must not be None.", None)
            )

            return self._result(violations)

        bindings = getattr(registry, "bindings", None)

        if bindings is None:
            violations.append(
                self._violation("MISSING_BINDINGS", "Registry must expose a bindings mapping.", None)
            )

            return self._result(violations)

        seen_pairs = set()

        for binding_id, binding in bindings.items():
            profile_id = getattr(binding, "profile_id", None)
            capability_id = getattr(binding, "capability_id", None)
            pair = (profile_id, capability_id)

            if profile_id is not None and capability_id is not None and pair in seen_pairs:
                violations.append(
                    self._violation(
                        "DUPLICATE_BINDING_PAIR",
                        f"Profile ID {profile_id!r} and capability ID {capability_id!r} are bound more than once; "
                        "(profile_id, capability_id) pairs must be unique.",
                        binding_id,
                    )
                )

            seen_pairs.add(pair)

            binding_result = self.validate(binding)

            for violation in binding_result.violations:
                violations.append(violation)

        return self._result(violations)

    def validate_resolution(
        self,
        result,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult:
        """
        Validate a resolution result produced by a binding resolver.

        Checks that the result is not None, that a resolved result
        carries a valid binding, and that an unresolved result
        carries neither a binding nor a resolution source.

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
        binding = getattr(result, "binding", None)
        source = getattr(result, "source", None)

        if resolved is True:
            if binding is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_BINDING",
                        "A resolved resolution result must carry a binding.",
                        None,
                    )
                )
            else:
                binding_result = self.validate(binding)

                for violation in binding_result.violations:
                    violations.append(violation)

            if source is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_SOURCE",
                        "A resolved resolution result must carry a resolution source.",
                        None,
                    )
                )

        elif resolved is False:
            if binding is not None:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_BINDING",
                        "An unresolved resolution result must not carry a binding.",
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
        binding_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationViolation:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationViolation(
            code=code,
            message=message,
            binding_id=binding_id,
        )

    def _result(
        self,
        violations,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult(
            valid=len(violations) == 0,
            violations=tuple(violations),
        )
