from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationViolation,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile binding templates,
    registries, and resolution results before registration or
    instantiation, guaranteeing structural integrity.

    The validator's responsibility is checking and reporting, not
    registration, instantiation, or repair. It does NOT register
    templates, instantiate templates, mutate its inputs, raise on
    invalid input, persist results, log, or publish events.

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
                referenced binding exists. Any object exposing a
                `contains(binding_id)` lookup is accepted
        """

        self._binding_registry = binding_registry

    def validate(
        self,
        template,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult:
        """
        Validate a single binding template.

        Checks that the template is not None, that its template ID and
        name are present and non-blank, that its referenced bindings
        are unique, and that every referenced binding exists in the
        configured binding registry.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the template is valid
        """

        violations = []

        if template is None:
            violations.append(
                self._violation("MISSING_TEMPLATE", "Template must not be None.", None)
            )

            return self._result(violations)

        template_id = getattr(template, "template_id", None)

        if template_id is None or not template_id.strip():
            violations.append(
                self._violation("MISSING_TEMPLATE_ID", "Template must have a non-blank template ID.", template_id)
            )

        name = getattr(template, "name", None)

        if name is None or not name.strip():
            violations.append(
                self._violation("MISSING_TEMPLATE_NAME", "Template must have a non-blank name.", template_id)
            )

        binding_ids = getattr(template, "binding_ids", None)

        if binding_ids is None:
            violations.append(
                self._violation("MISSING_BINDING_IDS", "Template must expose a binding_ids collection.", template_id)
            )
        else:
            seen_binding_ids = set()

            for binding_id in binding_ids:
                if binding_id is None or not str(binding_id).strip():
                    violations.append(
                        self._violation(
                            "MISSING_MEMBER_BINDING_ID",
                            "Template referenced binding ID must be non-blank.",
                            template_id,
                        )
                    )

                    continue

                if binding_id in seen_binding_ids:
                    violations.append(
                        self._violation(
                            "DUPLICATE_MEMBER",
                            f"Binding ID {binding_id!r} is referenced by the template more than once; "
                            "template references must be unique.",
                            template_id,
                        )
                    )

                seen_binding_ids.add(binding_id)

                if not self._binding_registry.contains(binding_id):
                    violations.append(
                        self._violation(
                            "UNKNOWN_BINDING",
                            f"Binding ID {binding_id!r} is not registered in the binding registry.",
                            template_id,
                        )
                    )

        return self._result(violations)

    def validate_registry(
        self,
        registry,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult:
        """
        Validate every template registered in a binding template
        registry.

        Args:
            registry: The registry to validate. Any object exposing
                a `templates` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found across every registered template, empty if the
            registry is valid
        """

        violations = []

        if registry is None:
            violations.append(
                self._violation("MISSING_REGISTRY", "Registry must not be None.", None)
            )

            return self._result(violations)

        templates = getattr(registry, "templates", None)

        if templates is None:
            violations.append(
                self._violation("MISSING_TEMPLATES", "Registry must expose a templates mapping.", None)
            )

            return self._result(violations)

        for template in templates.values():
            template_result = self.validate(template)

            for violation in template_result.violations:
                violations.append(violation)

        return self._result(violations)

    def validate_resolution(
        self,
        result,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult:
        """
        Validate a resolution result produced by a binding template
        resolver.

        Checks that the result is not None, that a resolved result
        carries a valid template and a resolution source, and that an
        unresolved result carries neither a template, member
        bindings, nor a resolution source.

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
        template = getattr(result, "template", None)
        bindings = getattr(result, "bindings", None)
        source = getattr(result, "source", None)

        if resolved is True:
            if template is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_TEMPLATE",
                        "A resolved resolution result must carry a template.",
                        None,
                    )
                )
            else:
                template_result = self.validate(template)

                for violation in template_result.violations:
                    violations.append(violation)

            if source is None:
                violations.append(
                    self._violation(
                        "RESOLVED_MISSING_SOURCE",
                        "A resolved resolution result must carry a resolution source.",
                        getattr(template, "template_id", None),
                    )
                )

        elif resolved is False:
            if template is not None:
                violations.append(
                    self._violation(
                        "UNRESOLVED_CARRIES_TEMPLATE",
                        "An unresolved resolution result must not carry a template.",
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
        template_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationViolation:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationViolation(
            code=code,
            message=message,
            template_id=template_id,
        )

    def _result(
        self,
        violations,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateValidationResult(
            valid=len(violations) == 0,
            violations=tuple(violations),
        )
