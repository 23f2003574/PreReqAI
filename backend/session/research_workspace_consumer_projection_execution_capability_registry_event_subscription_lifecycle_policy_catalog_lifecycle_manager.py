from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_lifecycle import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycle,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_lifecycle_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_lifecycle_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager:
    """
    Transitions a consumer projection execution capability registry
    event subscription lifecycle policy catalog through its
    operational lifecycle: DRAFT -> ACTIVE -> DEPRECATED -> ARCHIVED,
    with ACTIVE also able to transition directly to ARCHIVED.

    The manager's responsibility is lifecycle transition validation
    and tracking, not catalog mutation, evaluation, or
    synchronization. It does NOT build catalogs from scratch,
    mutate catalog metadata or policies, evaluate policies, execute
    lifecycle transitions of subscriptions, persist lifecycle
    state externally, log, or publish events.

    Like the backup service, the manager is not fully stateless: it
    tracks each catalog's lifecycle by the catalog's object
    identity, since no external lifecycle carrier is passed into
    activate(), deprecate(), archive(), or state(). A catalog never
    tracked before is treated as DRAFT. The manager never mutates
    the catalogs it is given.
    """

    _VALID_TRANSITIONS = {
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DRAFT: frozenset(
            {
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ACTIVE,
            }
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ACTIVE: frozenset(
            {
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DEPRECATED,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ARCHIVED,
            }
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DEPRECATED: frozenset(
            {
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ARCHIVED,
            }
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ARCHIVED: frozenset(),
    }

    def __init__(
        self,
    ):

        self._lifecycle_by_catalog_id = {}

    def activate(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult:
        """
        Transition a policy catalog from DRAFT to ACTIVE.

        Args:
            catalog: The policy catalog to activate

        Returns:
            An immutable lifecycle result carrying the catalog's
            previous and current states

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError:
                If the catalog is invalid or is not currently DRAFT
        """

        return self._transition(

            catalog,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ACTIVE,

            "activated_at",
        )

    def deprecate(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult:
        """
        Transition a policy catalog from ACTIVE to DEPRECATED.

        Args:
            catalog: The policy catalog to deprecate

        Returns:
            An immutable lifecycle result carrying the catalog's
            previous and current states

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError:
                If the catalog is invalid or is not currently ACTIVE
        """

        return self._transition(

            catalog,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DEPRECATED,

            "deprecated_at",
        )

    def archive(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult:
        """
        Transition a policy catalog from ACTIVE or DEPRECATED to
        ARCHIVED.

        Args:
            catalog: The policy catalog to archive

        Returns:
            An immutable lifecycle result carrying the catalog's
            previous and current states

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError:
                If the catalog is invalid or is not currently ACTIVE
                or DEPRECATED
        """

        return self._transition(

            catalog,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ARCHIVED,

            "archived_at",
        )

    def state(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState:
        """
        Read a policy catalog's current lifecycle state.

        Args:
            catalog: The policy catalog to inspect

        Returns:
            The catalog's current lifecycle state; a catalog never
            transitioned before is DRAFT

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError:
                If the catalog is invalid
        """

        self._validate_catalog(
            catalog
        )

        return self._current_lifecycle(
            catalog
        ).state

    def _transition(

        self,

        catalog,

        target_state,

        timestamp_field,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult:

        self._validate_catalog(
            catalog
        )

        current_lifecycle = self._current_lifecycle(
            catalog
        )

        allowed_next_states = self._VALID_TRANSITIONS.get(
            current_lifecycle.state,

            frozenset(),
        )

        if target_state not in allowed_next_states:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot transition a policy catalog from "
                    f"{current_lifecycle.state!r} to {target_state!r}."
                )
            )

        timestamps = {
            "activated_at": current_lifecycle.activated_at,

            "deprecated_at": current_lifecycle.deprecated_at,

            "archived_at": current_lifecycle.archived_at,
        }

        timestamps[timestamp_field] = datetime.now(
            timezone.utc
        )

        updated_lifecycle = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycle(
                state=target_state,

                activated_at=timestamps["activated_at"],

                deprecated_at=timestamps["deprecated_at"],

                archived_at=timestamps["archived_at"],
            )
        )

        self._lifecycle_by_catalog_id[
            id(
                catalog
            )
        ] = updated_lifecycle

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult(
                previous_state=current_lifecycle.state,

                current_state=target_state,

                catalog=catalog,
            )
        )

    def _validate_catalog(

        self,

        catalog,

    ) -> None:

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot manage the lifecycle of a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot manage the lifecycle of a policy catalog with missing "
                    "metadata."
                )
            )

        if catalog.policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot manage the lifecycle of a policy catalog with None "
                    "policies."
                )
            )

    def _current_lifecycle(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycle:

        key = id(
            catalog
        )

        if key not in self._lifecycle_by_catalog_id:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycle(
                    state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DRAFT,

                    activated_at=None,

                    deprecated_at=None,

                    archived_at=None,
                )
            )

        lifecycle = self._lifecycle_by_catalog_id[key]

        if lifecycle is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot manage the lifecycle of a catalog with missing "
                    "lifecycle metadata."
                )
            )

        if not isinstance(

            lifecycle.state,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError(
                    "Cannot manage the lifecycle of a catalog with an invalid "
                    f"lifecycle state: {lifecycle.state!r}."
                )
            )

        return lifecycle
