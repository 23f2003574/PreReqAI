from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_inheritance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_inheritance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritance,
    VALID_SESSION_POLICY_INHERITANCE_FIELDS,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_effective_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionEffectivePolicy,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceService:
    """
    Links consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session policies into single-parent inheritance hierarchies, and
    resolves each policy's fully merged, effective configuration by
    cascading ancestor configuration down through each link's
    selective overrides.

    The service's responsibility is the inheritance graph and its
    resolution, not the base policy service. It does NOT read from or
    write to the existing session policy service; a caller is
    expected to call resolve() wherever it would otherwise read a
    policy's own configuration directly, and to hand this service the
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy
    objects it links.

    Behavior:
    - A policy may have at most one parent at a time; link() rejects
      a child that already has a parent until it is unlink()-ed
    - A field is treated as overridden by a child, and cascades that
      child's own value instead of its parent's, whenever the two
      differ; this is computed automatically at link() time, not
      supplied by the caller
    - link() rejects any link that would create a cycle in the
      inheritance graph
    - resolve() caches its result per policy_id; link() and unlink()
      both invalidate the entire cache, since either can change what
      any policy resolves to

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._parent_by_child = {}
        self._inheritance_by_child = {}
        self._cache = {}
        self._lock = RLock()

    def link(
        self,
        child: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
        parent: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritance:
        """
        Make parent the single parent of child, computing which of
        child's fields are overridden by comparing them to parent's.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError:
                If child or parent is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
                child.policy_id equals parent.policy_id, child already
                has a parent, or the link would create a cycle
        """

        for policy, label in ((child, "child"), (parent, "parent")):
            if not isinstance(policy, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Cannot link an invalid {label}: {label} must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy."
                )

        with self._lock:
            if child.policy_id in self._parent_by_child:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Policy ID {child.policy_id!r} already has a parent; unlink it first."
                )

            if self._would_cycle(child.policy_id, parent.policy_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Cannot link policy ID {child.policy_id!r} to parent ID {parent.policy_id!r}: it would "
                    "create an inheritance cycle."
                )

            overridden_fields = tuple(
                sorted(
                    field_name
                    for field_name in VALID_SESSION_POLICY_INHERITANCE_FIELDS
                    if getattr(child, field_name) != getattr(parent, field_name)
                )
            )

            inheritance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritance(
                child_policy_id=child.policy_id,
                parent_policy_id=parent.policy_id,
                overridden_fields=overridden_fields,
            )

            self._policies_by_id[child.policy_id] = child
            self._policies_by_id[parent.policy_id] = parent
            self._parent_by_child[child.policy_id] = parent.policy_id
            self._inheritance_by_child[child.policy_id] = inheritance
            self._cache.clear()

            return inheritance

    def unlink(self, child_policy_id: str) -> None:
        """
        Remove a policy's single parent link.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError:
                If child_policy_id is None or blank, or it currently
                has no parent
        """

        self._validate_id(child_policy_id, "child policy ID")

        with self._lock:
            if child_policy_id not in self._parent_by_child:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Policy ID {child_policy_id!r} has no parent to unlink."
                )

            del self._parent_by_child[child_policy_id]
            del self._inheritance_by_child[child_policy_id]
            self._cache.clear()

    def resolve(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionEffectivePolicy:
        """
        Resolve a policy's fully merged, effective configuration,
        wherever a caller would otherwise read a policy's own
        configuration directly.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError:
                If policy_id is None or blank, no policy is known
                under it, or its inheritance chain contains a cycle
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            self._resolve_known(policy_id)

            if policy_id in self._cache:
                return self._cache[policy_id]

            chain = self._chain(policy_id)
            configuration = {}

            for depth, current_id in enumerate(reversed(chain)):
                policy = self._policies_by_id[current_id]

                if depth == 0:
                    for field_name in VALID_SESSION_POLICY_INHERITANCE_FIELDS:
                        configuration[field_name] = getattr(policy, field_name)
                else:
                    inheritance = self._inheritance_by_child[current_id]

                    for field_name in inheritance.overridden_fields:
                        configuration[field_name] = getattr(policy, field_name)

            effective = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionEffectivePolicy(
                policy_id=policy_id,
                resolved_configuration=configuration,
            )

            self._cache[policy_id] = effective

            return effective

    def lineage(self, policy_id: str) -> tuple:
        """
        List a policy's own ID followed by each ancestor's ID, from
        nearest parent to furthest ancestor.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError:
                If policy_id is None or blank, no policy is known
                under it, or its inheritance chain contains a cycle
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            self._resolve_known(policy_id)

            return tuple(self._chain(policy_id))

    def validate(self, policy_id: str) -> bool:
        """
        Confirm a policy's inheritance chain contains no cycle.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError:
                If policy_id is None or blank, no policy is known
                under it, or its inheritance chain contains a cycle
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            self._resolve_known(policy_id)
            self._chain(policy_id)

            return True

    def _would_cycle(self, child_policy_id: str, parent_policy_id: str) -> bool:
        current = parent_policy_id

        while current is not None:
            if current == child_policy_id:
                return True

            current = self._parent_by_child.get(current)

        return False

    def _chain(self, policy_id: str) -> list:
        chain = []
        seen = set()
        current = policy_id

        while current is not None:
            if current in seen:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Inheritance cycle detected involving policy ID {current!r}."
                )

            seen.add(current)
            chain.append(current)
            current = self._parent_by_child.get(current)

        return chain

    def _resolve_known(self, policy_id: str) -> None:
        if policy_id not in self._policies_by_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                f"No policy is known under policy ID {policy_id!r}."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                f"Cannot operate with an empty or blank {label}."
            )
