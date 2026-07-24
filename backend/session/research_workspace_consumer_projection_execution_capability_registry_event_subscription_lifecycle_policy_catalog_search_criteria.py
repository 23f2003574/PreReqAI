from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_search_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError,
)


def _validate_identifier_collection(

    identifiers,

    label,

):

    if identifiers is None:

        return

    seen_identifiers = set()

    for identifier in identifiers:

        if not identifier:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    f"Cannot search with a blank {label} identifier."
                )
            )

        if identifier in seen_identifiers:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    f"Cannot search with duplicate {label} identifier '{identifier}'."
                )
            )

        seen_identifiers.add(
            identifier
        )


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria:
    """
    Immutable criteria describing which policies in a consumer
    projection execution capability registry event subscription
    lifecycle policy catalog should be matched by a search.

    The criteria is a value object only. It performs no catalog
    lookup and no search.

    Attributes:
        identifier_prefix: If set, only identifiers starting with
            this prefix match
        identifier_contains: If set, only identifiers containing
            this substring match
        include_identifiers: If set, only these identifiers are
            eligible to match
        exclude_identifiers: If set, these identifiers never match
    """

    identifier_prefix: (
        str | None
    ) = None

    identifier_contains: (
        str | None
    ) = None

    include_identifiers: (
        tuple[str, ...] | None
    ) = None

    exclude_identifiers: (
        tuple[str, ...] | None
    ) = None

    def __post_init__(self):

        if (

            self.identifier_prefix is not None

            and not self.identifier_prefix
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    "Cannot search with a blank identifier prefix."
                )
            )

        if (

            self.identifier_contains is not None

            and not self.identifier_contains
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    "Cannot search with a blank identifier substring."
                )
            )

        _validate_identifier_collection(
            self.include_identifiers,

            "include",
        )

        _validate_identifier_collection(
            self.exclude_identifiers,

            "exclude",
        )
