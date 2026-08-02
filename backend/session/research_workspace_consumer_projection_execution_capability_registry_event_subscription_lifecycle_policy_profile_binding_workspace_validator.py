from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_validation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationViolation,
)


_EXPECTED_RESOURCE_KINDS = frozenset({"bindings", "templates", "presets", "groups"})


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidator:
    """
    Validates consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspaces,
    registries, and snapshots before registration, cloning, or
    snapshot creation, guaranteeing structural integrity.

    The validator's responsibility is checking and reporting, not
    registration, cloning, snapshot creation, or repair. It does NOT
    register workspaces, clone workspaces, create snapshots, mutate
    its inputs, raise on invalid input, persist results, log, or
    publish events.

    The validator is:
    - Stateless: No mutable instance state; the member registries it
      was constructed with are treated as read-only
    - Deterministic: Same input and registry state always produce the
      same result
    - Side-effect free: Never mutates its inputs or the registries
    - Exhaustive: Accumulates every violation found rather than
      stopping at the first one
    """

    def __init__(self, binding_registry, template_registry, preset_registry, group_registry):
        """
        Args:
            binding_registry: The registry used to verify that a
                referenced binding exists. Any object exposing a
                `contains(binding_id)` lookup is accepted
            template_registry: The registry used to verify that a
                referenced binding template exists. Any object
                exposing a `contains(template_id)` lookup is accepted
            preset_registry: The registry used to verify that a
                referenced binding preset exists. Any object exposing
                a `contains(preset_id)` lookup is accepted
            group_registry: The registry used to verify that a
                referenced binding group exists. Any object exposing
                a `contains(group_id)` lookup is accepted
        """

        self._binding_registry = binding_registry
        self._template_registry = template_registry
        self._preset_registry = preset_registry
        self._group_registry = group_registry

    def validate(
        self,
        workspace,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult:
        """
        Validate a single binding workspace.

        Checks that the workspace is not None, that its workspace ID
        and name are present and non-blank, that each of its four
        referenced resource collections (bindings, binding templates,
        binding presets, binding groups) contains only unique,
        non-blank identifiers, and that every referenced resource
        exists in its corresponding configured registry.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the workspace is valid
        """

        violations = []

        if workspace is None:
            violations.append(
                self._violation("MISSING_WORKSPACE", "Workspace must not be None.", None)
            )

            return self._result(violations)

        workspace_id = getattr(workspace, "workspace_id", None)

        if workspace_id is None or not workspace_id.strip():
            violations.append(
                self._violation("MISSING_WORKSPACE_ID", "Workspace must have a non-blank workspace ID.", workspace_id)
            )

        name = getattr(workspace, "name", None)

        if name is None or not name.strip():
            violations.append(
                self._violation("MISSING_WORKSPACE_NAME", "Workspace must have a non-blank name.", workspace_id)
            )

        for label, attribute, registry, unknown_code in (
            ("binding", "binding_ids", self._binding_registry, "UNKNOWN_BINDING"),
            ("binding template", "template_ids", self._template_registry, "UNKNOWN_TEMPLATE"),
            ("binding preset", "preset_ids", self._preset_registry, "UNKNOWN_PRESET"),
            ("binding group", "group_ids", self._group_registry, "UNKNOWN_GROUP"),
        ):
            member_ids = getattr(workspace, attribute, None)

            if member_ids is None:
                violations.append(
                    self._violation(
                        f"MISSING_{attribute.upper()}",
                        f"Workspace must expose a {attribute} collection.",
                        workspace_id,
                    )
                )

                continue

            seen_member_ids = set()

            for member_id in member_ids:
                if member_id is None or not str(member_id).strip():
                    violations.append(
                        self._violation(
                            "MISSING_MEMBER_ID",
                            f"Workspace referenced {label} ID must be non-blank.",
                            workspace_id,
                        )
                    )

                    continue

                if member_id in seen_member_ids:
                    violations.append(
                        self._violation(
                            "DUPLICATE_MEMBER",
                            f"{label.capitalize()} ID {member_id!r} is referenced by the workspace more than "
                            "once; workspace references must be unique.",
                            workspace_id,
                        )
                    )

                    continue

                seen_member_ids.add(member_id)

                if not registry.contains(member_id):
                    violations.append(
                        self._violation(
                            unknown_code,
                            f"{label.capitalize()} ID {member_id!r} is not registered in the {label} registry.",
                            workspace_id,
                        )
                    )

        return self._result(violations)

    def validate_registry(
        self,
        registry,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult:
        """
        Validate every workspace registered in a binding workspace
        registry.

        Args:
            registry: The registry to validate. Any object exposing
                a `workspaces` mapping is accepted

        Returns:
            An immutable validation result carrying every violation
            found across every registered workspace, empty if the
            registry is valid
        """

        violations = []

        if registry is None:
            violations.append(
                self._violation("MISSING_REGISTRY", "Registry must not be None.", None)
            )

            return self._result(violations)

        workspaces = getattr(registry, "workspaces", None)

        if workspaces is None:
            violations.append(
                self._violation("MISSING_WORKSPACES", "Registry must expose a workspaces mapping.", None)
            )

            return self._result(violations)

        for workspace in workspaces.values():
            workspace_result = self.validate(workspace)

            for violation in workspace_result.violations:
                violations.append(violation)

        return self._result(violations)

    def validate_snapshot(
        self,
        snapshot,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult:
        """
        Validate a snapshot produced by a binding workspace service.

        Checks that the snapshot is not None, that it carries a
        non-blank workspace ID and a created_at instant, and that its
        resource_counts carries exactly the expected resource kinds
        ("bindings", "templates", "presets", "groups"), each mapped to
        a non-negative integer count.

        Returns:
            An immutable validation result carrying every violation
            found, empty if the snapshot is valid
        """

        violations = []

        if snapshot is None:
            violations.append(
                self._violation("MISSING_SNAPSHOT", "Snapshot must not be None.", None)
            )

            return self._result(violations)

        workspace_id = getattr(snapshot, "workspace_id", None)

        if workspace_id is None or not workspace_id.strip():
            violations.append(
                self._violation(
                    "MISSING_SNAPSHOT_WORKSPACE_ID",
                    "Snapshot must have a non-blank workspace ID.",
                    workspace_id,
                )
            )

        created_at = getattr(snapshot, "created_at", None)

        if created_at is None:
            violations.append(
                self._violation(
                    "MISSING_SNAPSHOT_CREATED_AT",
                    "Snapshot must have a created_at instant.",
                    workspace_id,
                )
            )

        resource_counts = getattr(snapshot, "resource_counts", None)

        if resource_counts is None:
            violations.append(
                self._violation(
                    "MISSING_RESOURCE_COUNTS",
                    "Snapshot must expose a resource_counts mapping.",
                    workspace_id,
                )
            )
        elif set(resource_counts) != _EXPECTED_RESOURCE_KINDS:
            violations.append(
                self._violation(
                    "INVALID_RESOURCE_COUNTS",
                    "Snapshot resource_counts must carry exactly the expected resource kinds: "
                    f"{sorted(_EXPECTED_RESOURCE_KINDS)}.",
                    workspace_id,
                )
            )
        else:
            for kind, count in resource_counts.items():
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    violations.append(
                        self._violation(
                            "INVALID_RESOURCE_COUNT",
                            f"Snapshot resource count for {kind!r} must be a non-negative integer.",
                            workspace_id,
                        )
                    )

        return self._result(violations)

    def _violation(
        self,
        code,
        message,
        workspace_id,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationViolation:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationViolation(
            code=code,
            message=message,
            workspace_id=workspace_id,
        )

    def _result(
        self,
        violations,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult:
        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult(
            valid=len(violations) == 0,
            violations=tuple(violations),
        )
