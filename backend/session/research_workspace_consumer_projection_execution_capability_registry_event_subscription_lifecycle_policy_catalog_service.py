from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogService:
    """
    Provides read-only discovery over a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog.

    The service's responsibility is lookup and discovery only. It
    does NOT build catalogs, validate catalogs, mutate catalogs,
    evaluate policies, execute lifecycle transitions, persist data,
    log, or publish events.

    The service is:
    - Stateless: Holds only a reference to the catalog it was
      constructed with
    - Deterministic: Same catalog and identifier always produce the
      same outcome
    - Side-effect free: Never mutates the catalog
    """

    def __init__(

        self,

        catalog,

    ):
        """
        Args:
            catalog: The policy catalog to serve read-only discovery
                operations over

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError:
                If the catalog is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                    "Cannot serve discovery over a None policy catalog."
                )
            )

        self._catalog = catalog

    def contains(

        self,

        identifier,

    ) -> bool:
        """
        Check whether a policy is registered under an identifier.

        Args:
            identifier: The policy identifier to check

        Returns:
            True if a policy is registered under the identifier,
            False otherwise
        """

        return identifier in self._catalog.policies

    def find(

        self,

        identifier,

    ):
        """
        Find the policy registered under an identifier.

        Args:
            identifier: The policy identifier to look up

        Returns:
            The policy registered under the identifier, or None if
            no policy is registered under it
        """

        return self._catalog.policies.get(
            identifier
        )

    def list(
        self,
    ) -> tuple:
        """
        List every policy in the catalog.

        Returns:
            An immutable tuple of every policy in the catalog,
            preserving catalog ordering
        """

        return tuple(
            self._catalog.policies.values()
        )

    def identifiers(
        self,
    ) -> tuple:
        """
        List every policy identifier in the catalog.

        Returns:
            An immutable tuple of every policy identifier in the
            catalog, preserving catalog ordering
        """

        return tuple(
            self._catalog.policies.keys()
        )

    def metadata(
        self,
    ):
        """
        Returns:
            The catalog's descriptive metadata
        """

        return self._catalog.metadata
