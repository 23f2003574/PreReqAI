from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_inheritance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_inheritance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_inheritance_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceService:
    """
    Manages and resolves hierarchical profile assignment inheritance links
    among targets.

    This service allows targets to inherit policy profile assignments from
    parent scopes. If a target does not have a local profile assignment,
    its hierarchy is traversed upwards until a profile assignment is found.

    The service is:
    - Thread-safe: Mutex-guarded read and write operations
    - Cycle-free: Rejects establishing parent-child relationships that introduce cycle loop
    - Depth-limited: Configurable maximum inheritance depth limit to protect recursive resolution
    - Stateless: Does not store profile definitions or active profiles; depends on an external
      profile assignment registry service
    """

    def __init__(self, assignment_registry_service, max_depth: int = 10):
        """
        Args:
            assignment_registry_service: Any object exposing find(target_id) and contains(target_id)
            max_depth: Maximum hierarchy height limit allowed for resolution traversal
        """
        if assignment_registry_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                "Cannot initialize inheritance service with a None assignment registry service."
            )

        self._assignment_registry_service = assignment_registry_service
        self._max_depth = max_depth
        self._parents = {}  # target_id -> parent_target_id
        self._lock = RLock()

    def inherit(self, target_id: str, parent_target_id: str) -> None:
        """
        Establishes an inheritance link where target_id inherits profile assignments
        from parent_target_id.

        Args:
            target_id: The child target ID
            parent_target_id: The parent target ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError:
                If target_id or parent_target_id is None/blank, parent target does not exist,
                self-inheritance is attempted, cycle loop is introduced, or maximum depth limit is exceeded.
        """
        self._validate_id(target_id, "target ID")
        self._validate_id(parent_target_id, "parent target ID")

        if target_id == parent_target_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                f"Cannot inherit from self: target ID {target_id!r}."
            )

        with self._lock:
            # Check if parent target exists (either has local assignment or is already configured in hierarchy)
            # Or if the registry contains the parent
            parent_exists = (
                self._assignment_registry_service.contains(parent_target_id)
                or parent_target_id in self._parents
                or parent_target_id in self._parents.values()
            )

            if not parent_exists:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                    f"Parent target ID {parent_target_id!r} is missing / not registered."
                )

            # Store old parent for backtracking in case of validation failure
            old_parent = self._parents.get(target_id)
            self._parents[target_id] = parent_target_id

            try:
                # Cycle detection
                visited = set()
                curr = target_id
                while curr in self._parents:
                    if curr in visited:
                        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                            f"Cyclic inheritance detected involving target ID {curr!r}."
                        )
                    visited.add(curr)
                    curr = self._parents[curr]

                # Depth limit check: check length of path from any node
                for node in list(self._parents.keys()) + list(self._parents.values()):
                    depth = 0
                    curr = node
                    while curr in self._parents:
                        depth += 1
                        if depth > self._max_depth:
                            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                                f"Max inheritance depth limit of {self._max_depth} exceeded."
                            )
                        curr = self._parents[curr]
            except Exception:
                # Restore previous parent relationship
                if old_parent is None:
                    self._parents.pop(target_id, None)
                else:
                    self._parents[target_id] = old_parent
                raise

    def break_inheritance(self, target_id: str) -> None:
        """
        Removes the inheritance link for the target_id.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError:
                If target_id is None/blank or the target is not currently inheriting.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            if target_id not in self._parents:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                    f"Target ID {target_id!r} is not currently configured to inherit from any parent."
                )
            del self._parents[target_id]

    def resolve_effective(
        self, target_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult:
        """
        Walks up the parent hierarchy to resolve the effective profile ID.
        Local assignments always override parent/ancestor assignments.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            # Walk parent hierarchy to capture path
            path = []
            curr = target_id
            while curr in self._parents:
                parent = self._parents[curr]
                path.append((curr, parent))
                curr = parent

            # Check local assignment first
            local_assignment = self._assignment_registry_service.find(target_id)
            if local_assignment is not None:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult(
                    effective_profile_id=local_assignment.profile_id,
                    inherited=False,
                    inheritance_chain=()
                )

            # Search path starting from nearest parent
            effective_profile_id = None
            effective_index = -1
            for idx, (node, parent) in enumerate(path):
                assignment = self._assignment_registry_service.find(parent)
                if assignment is not None:
                    effective_profile_id = assignment.profile_id
                    effective_index = idx
                    break

            if effective_profile_id is None:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult(
                    effective_profile_id=None,
                    inherited=False,
                    inheritance_chain=()
                )

            # Construct inheritance chain
            chain_list = []
            for idx in range(effective_index + 1):
                node, parent = path[idx]
                depth = (effective_index - idx) + 1
                inheritance_obj = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritance(
                    target_id=node,
                    parent_target_id=parent,
                    inherited_profile_id=effective_profile_id,
                    inheritance_depth=depth
                )
                chain_list.append(inheritance_obj)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceResult(
                effective_profile_id=effective_profile_id,
                inherited=True,
                inheritance_chain=tuple(chain_list)
            )

    def inheritance_chain(self, target_id: str) -> tuple:
        """
        Returns the resolved inheritance chain for target_id.
        """
        self._validate_id(target_id, "target ID")
        return self.resolve_effective(target_id).inheritance_chain

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentInheritanceError(
                f"Cannot perform inheritance operation with an empty or blank {label}."
            )
