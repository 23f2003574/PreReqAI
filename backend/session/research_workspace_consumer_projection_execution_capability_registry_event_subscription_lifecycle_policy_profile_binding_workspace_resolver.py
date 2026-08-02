from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver:
    """
    Resolves the effective consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace, and the counts and identities of its eligible member
    bindings, binding templates, binding presets, and binding groups,
    for a workspace identifier, providing a single lookup interface
    for downstream editing and deployment components.

    The resolver's responsibility is centralized, deterministic
    resolution of the effective workspace and its members for a given
    workspace ID, not workspace creation, replacement, removal,
    validation, or persistence. It does NOT create workspaces, mutate
    a registry, validate workspaces, persist results, log, or publish
    events. A resolver works against any object exposing a
    `find(workspace_id)` lookup, such as a binding workspace registry
    service, together with a registry and an activation service
    exposing `state(member_id)` for each of the four member resource
    kinds. Only a member that is both registered and ACTIVE is
    included among a workspace's resolved members; missing and
    inactive members are silently skipped, and members are returned
    in the order they are stored on the workspace.

    The resolver is:
    - Stateless: No mutable instance state; the registries, activation
      services, and default workspace it was constructed with are
      treated as read-only
    - Deterministic: Same workspace ID and registry state always
      produce the same outcome
    - Side-effect free: Never mutates the workspace registry, any
      member registry, or any activation service it resolves against
    """

    def __init__(
        self,
        workspace_registry,
        binding_registry,
        binding_activation_service,
        template_registry,
        template_activation_service,
        preset_registry,
        preset_activation_service,
        group_registry,
        group_activation_service,
        default_workspace=None,
    ):
        """
        Args:
            workspace_registry: The primary lookup source to resolve
                against. Any object exposing a `find(workspace_id)`
                lookup is accepted
            binding_registry: The registry used to look up a
                workspace's member bindings. Any object exposing
                `find(binding_id)` is accepted
            binding_activation_service: The service used to check
                whether a member binding is eligible to participate in
                resolution. Any object exposing `state(binding_id)` is
                accepted
            template_registry: The registry used to look up a
                workspace's member binding templates. Any object
                exposing `find(template_id)` is accepted
            template_activation_service: The service used to check
                whether a member binding template is eligible to
                participate in resolution. Any object exposing
                `state(template_id)` is accepted
            preset_registry: The registry used to look up a
                workspace's member binding presets. Any object
                exposing `find(preset_id)` is accepted
            preset_activation_service: The service used to check
                whether a member binding preset is eligible to
                participate in resolution. Any object exposing
                `state(preset_id)` is accepted
            group_registry: The registry used to look up a
                workspace's member binding groups. Any object exposing
                `find(group_id)` is accepted
            group_activation_service: The service used to check
                whether a member binding group is eligible to
                participate in resolution. Any object exposing
                `state(group_id)` is accepted
            default_workspace: An optional workspace to fall back to
                when the registry has no workspace for the workspace
                ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError:
                If any registry or activation service is None
        """

        self._collaborators = {
            "workspace registry": workspace_registry,
            "binding registry": binding_registry,
            "binding activation service": binding_activation_service,
            "binding template registry": template_registry,
            "binding template activation service": template_activation_service,
            "binding preset registry": preset_registry,
            "binding preset activation service": preset_activation_service,
            "binding group registry": group_registry,
            "binding group activation service": group_activation_service,
        }

        for label, collaborator in self._collaborators.items():
            if collaborator is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                    f"Cannot resolve binding workspaces against a None {label}."
                )

        self._workspace_registry = workspace_registry
        self._binding_registry = binding_registry
        self._binding_activation_service = binding_activation_service
        self._template_registry = template_registry
        self._template_activation_service = template_activation_service
        self._preset_registry = preset_registry
        self._preset_activation_service = preset_activation_service
        self._group_registry = group_registry
        self._group_activation_service = group_activation_service
        self._default_workspace = default_workspace

    def resolve(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResult:
        """
        Resolve the effective binding workspace, and the counts of its
        eligible member resources, for a workspace ID.

        The workspace registry is consulted first. If it has no
        workspace for the workspace ID and a default workspace was
        configured, the default workspace is used instead.

        Returns:
            An immutable resolution result. If no workspace is found
            in any configured source, resolved is False, workspace is
            None, resource_counts is empty, and source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError:
                If the workspace ID is None or blank, or the resolved
                workspace's membership is corrupted
        """

        self._validate_workspace_id(workspace_id)

        workspace = self._workspace_registry.find(workspace_id)
        source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource.REGISTRY

        if workspace is None:
            workspace = self._default_workspace
            source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource.DEFAULT

        if workspace is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResult(
                workspace=None,
                resolved=False,
                resource_counts={},
                source=None,
            )

        self._validate_workspace_membership(workspace)

        resources = self._resolve_all_members(workspace)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionResult(
            workspace=workspace,
            resolved=True,
            resource_counts={kind: len(members) for kind, members in resources.items()},
            source=source,
        )

    def resolve_or_raise(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
        """
        Resolve the effective binding workspace for a workspace ID,
        raising if it cannot be resolved.

        Returns:
            The resolved workspace

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError:
                If the workspace ID is None or blank, or no workspace
                could be resolved for it
        """

        result = self.resolve(workspace_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                f"Cannot resolve a binding workspace for workspace ID {workspace_id!r}: no workspace was found."
            )

        return result.workspace

    def contains(self, workspace_id: str) -> bool:
        """
        Check whether an effective binding workspace can be resolved
        for a workspace ID.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError:
                If the workspace ID is None or blank
        """

        return self.resolve(workspace_id).resolved

    def resolve_resources(self, workspace_id: str) -> dict:
        """
        Resolve a workspace's eligible member resources, in stored
        order.

        Returns:
            An immutable-shaped dict mapping resource kind
            ("bindings", "templates", "presets", "groups") to an
            immutable tuple of the workspace's registered, ACTIVE
            member resources of that kind, or a dict of empty tuples
            if the workspace cannot be resolved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError:
                If the workspace ID is None or blank
        """

        self._validate_workspace_id(workspace_id)

        result = self.resolve(workspace_id)

        if not result.resolved:
            return {"bindings": (), "templates": (), "presets": (), "groups": ()}

        return self._resolve_all_members(result.workspace)

    def _resolve_all_members(self, workspace) -> dict:
        return {
            "bindings": self._resolve_kind(
                workspace.binding_ids, self._binding_registry, self._binding_activation_service
            ),
            "templates": self._resolve_kind(
                workspace.template_ids, self._template_registry, self._template_activation_service
            ),
            "presets": self._resolve_kind(
                workspace.preset_ids, self._preset_registry, self._preset_activation_service
            ),
            "groups": self._resolve_kind(
                workspace.group_ids, self._group_registry, self._group_activation_service
            ),
        }

    def _resolve_kind(self, member_ids, registry, activation_service) -> tuple:
        resolved = []

        for member_id in member_ids:
            member = registry.find(member_id)

            if member is None:
                continue

            if (
                activation_service.state(member_id)
                != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
            ):
                continue

            resolved.append(member)

        return tuple(resolved)

    def _validate_workspace_id(self, workspace_id: str) -> None:
        if workspace_id is None or not workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                "Cannot resolve a binding workspace with an empty or blank workspace ID."
            )

    def _validate_workspace_membership(self, workspace) -> None:
        if not isinstance(
            workspace,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                "Cannot resolve a binding workspace: workspace membership is corrupted."
            )

        for member_ids in (
            workspace.binding_ids,
            workspace.template_ids,
            workspace.preset_ids,
            workspace.group_ids,
        ):
            try:
                member_ids = tuple(member_ids)
            except TypeError as error:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                    "Cannot resolve a binding workspace: workspace membership is corrupted."
                ) from error

            if any(
                member_id is None or not isinstance(member_id, str) or not member_id.strip()
                for member_id in member_ids
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError(
                    "Cannot resolve a binding workspace: workspace membership is corrupted."
                )
