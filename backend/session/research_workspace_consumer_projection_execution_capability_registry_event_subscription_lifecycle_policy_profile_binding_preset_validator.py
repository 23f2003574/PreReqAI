from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile binding presets,
    registries, and resolution results before registration or
    instantiation, guaranteeing structural integrity.

    The validator's responsibility is checking and reporting, not
    registration, instantiation, or repair. It does NOT register
    presets, instantiate presets, mutate its inputs, raise on invalid
    input, persist results, log, or publish events.

    The validator is:
    - Stateless: No mutable instance state; the template registry it
      was constructed with is treated as read-only
    - Deterministic: Same input and registry state always produce the
      same result
    - Side-effect free: Never mutates its inputs or the registries
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def __init__(self, template_registry):
        """
        Args:
            template_registry: The registry used to verify that a
                referenced binding template exists. Any object
                exposing a `contains(template_id)` lookup is accepted
        """

        self._template_registry = template_registry

    def validate(
        self,
        preset,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult:
        """
        Validate a single binding preset.

        Checks that the preset is not None, that its preset ID and
        name are present and non-blank, that its referenced binding
        templates are unique, and that every referenced binding
        template exists in the configured template registry.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the preset is valid
        """

        violations = []

        if preset is None:
            violations.append(
                self._violation("MISSING_PRESET", "Preset must not be None.", None)
            )

            return self._result(violations)

        preset_id = getattr(preset, "preset_id", None)

        if preset_id is None or not preset_id.strip():
            violations.append(
                self._violation("MISSING_PRESET_ID", "Preset must have a non-blank preset ID.", preset_id)
            )

        name = getattr(preset, "name", None)

        if name is None or not name.strip():
            violations.append(
                self._violation("MISSING_PRESET_NAME", "Preset must have a non-blank name.", preset_id)
            )

        binding_template_ids = getattr(preset, "binding_template_ids", None)

        if binding_template_ids is None:
            violations.append(
                self._violation(
                    "MISSING_TEMPLATE_IDS",
                    "Preset must expose a binding_template_ids collection.",
                    preset_id,
                )
            )
        else:
            seen_template_ids = set()

            for template_id in binding_template_ids:
                if template_id is None or not str(template_id).strip():
                    violations.append(
                        self._violation(
                            "MISSING_MEMBER_TEMPLATE_ID",
                            "Preset referenced template ID must be non-blank.",
                            preset_id,
                        )
                    )

                    continue

                if template_id in seen_template_ids:
                    violations.append(
                        self._violation(
                            "DUPLICATE_MEMBER",
                            f"Template ID {template_id!r} is referenced by the preset more than once; "
                            "preset references must be unique.",
                            preset_id,
                        )
                    )

                seen_template_ids.add(template_id)

                if not self._template_registry.contains(template_id):
                    violations.append(
                        self._violation(
                            "UNKNOWN_TEMPLATE",
                            f"Template ID {template_id!r} is not registered in the template registry.",
                            preset_id,
                        )
                    )

        return self._result(violations)

    def validate_registry(
        self,
        registry,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult:
        """
        Validate every preset registered in a binding preset registry.

        Args:
            registry: The registry to validate. Any object exposing
                a `presets` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found across every registered preset, empty if the
            registry is valid
        """

        violations = []

        if registry is None:
            violations.append(
                self._violation("MISSING_REGISTRY", "Registry must not be None.", None)
            )

            return self._result(violations)

        presets = getattr(registry, "presets", None)

        if presets is None:
            violations.append(
                self._violation("MISSING_PRESETS", "Registry must expose a presets mapping.", None)
            )

            return self._result(violations)

        for preset in presets.values():
            preset_result = self.validate(preset)

            for violation in preset_result.violations:
                violations.append(violation)

        return self._result(violations)

    def validate_resolution(
        self,
        result,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult:
        """
        Validate a resolution result produced by a binding preset
        resolver.

        Checks that the result is not None, that a resolved result
        carries a valid preset and a resolution source, and that an
        unresolved result carries neither a preset, member binding
        templates, nor a resolution source.

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
        preset = getattr(result, "preset", None)
        templates = getattr(result, "templates", None)
        source = getattr(result, "source", None)

        if resolved is True:
            if preset is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_PRESET",
                        "A resolved resolution result must carry a preset.",
                        None,
                    )
                )
            else:
                preset_result = self.validate(preset)

                for violation in preset_result.violations:
                    violations.append(violation)

            if source is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_SOURCE",
                        "A resolved resolution result must carry a resolution source.",
                        getattr(preset, "preset_id", None),
                    )
                )

        elif resolved is False:
            if preset is not None:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_PRESET",
                        "An unresolved resolution result must not carry a preset.",
                        None,
                    )
                )

            if templates:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_TEMPLATES",
                        "An unresolved resolution result must not carry member binding templates.",
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
        preset_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationViolation:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationViolation(
            code=code,
            message=message,
            preset_id=preset_id,
        )

    def _result(
        self,
        violations,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationResult(
            valid=len(violations) == 0,
            violations=tuple(violations),
        )
