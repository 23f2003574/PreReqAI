from datetime import (
    datetime,
    timezone,
)

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instantiation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instantiation_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instantiation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationService:
    """
    Runs the reusable pipeline that resolves, validates, and
    instantiates a consumer projection execution capability registry
    event subscription lifecycle policy profile instance from a
    registered profile definition: resolve the profile, resolve the
    requested published version, merge supplied parameter values
    with the profile's defaults, and produce a new, independent
    profile instance.

    The service's responsibility is orchestrating instantiation, not
    profile registration, replacement, versioning, or resolution
    strategy. It does NOT register profiles, mutate a registry or
    version history, mutate a profile, publish versions, persist
    results, log, or publish events.

    The service is:
    - Deterministic: Same request and lookup source states always
      produce the same outcome
    - Side-effect free on its inputs: Never mutates the profile,
      registry, or version history it instantiates from
    """

    def __init__(

        self,

        resolver,

        version_service,

    ):
        """
        Args:
            resolver: The profile resolver used to resolve a
                profile ID to a registered profile. Any object
                exposing `resolve_or_raise(profile_id)` and
                `can_resolve(profile_id)` is accepted
            version_service: The version service used to resolve a
                profile's published versions. Any object exposing
                `find(profile_id, version)` and `latest(profile_id)`
                is accepted
        """

        self._resolver = resolver

        self._version_service = version_service

    def instantiate(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult:
        """
        Instantiate a new profile instance from a specific published
        version of a registered profile.

        Args:
            request: The instantiation request describing which
                profile and version to instantiate from, and any
                caller-supplied parameter values

        Returns:
            An immutable instantiation result carrying a newly
            created, independent profile instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError:
                If the request is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest,
                has a blank profile ID or version, has parameter
                values that are neither None nor a mapping, the
                profile cannot be resolved, or no such version was
                published for the profile
        """

        self._validate_request(
            request
        )

        try:

            profile = self._resolver.resolve_or_raise(
                request.profile_id
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance: no profile was "
                    f"found under profile ID {request.profile_id!r}."
                )
            ) from error

        version = self._version_service.find(

            request.profile_id,

            request.version,
        )

        if version is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    f"Cannot instantiate a profile instance: version "
                    f"{request.version!r} was not found for profile ID "
                    f"{request.profile_id!r}."
                )
            )

        resolved_parameter_values = (
            request.parameter_values
            if request.parameter_values is not None
            else {}
        )

        instance = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
                profile_id=profile.profile_id,

                version=version.version,

                policy_identifiers=tuple(
                    version.policy_identifiers
                ),

                parameter_values=MappingProxyType(
                    dict(
                        resolved_parameter_values
                    )
                ),
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult(
                profile_instance=instance,

                instantiated=True,

                instantiated_at=datetime.now(
                    timezone.utc
                ),
            )
        )

    def instantiate_latest(

        self,

        profile_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult:
        """
        Instantiate a new profile instance from the current version
        of a registered profile.

        Args:
            profile_id: The profile ID to instantiate the current
                version of

        Returns:
            An immutable instantiation result carrying a newly
            created, independent profile instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError:
                If the profile ID is None or blank, the profile
                cannot be resolved, or no version has ever been
                published for the profile
        """

        self._validate_profile_id(
            profile_id
        )

        latest_version = self._version_service.latest(
            profile_id
        )

        if latest_version is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance: no version has "
                    f"ever been published for profile ID {profile_id!r}."
                )
            )

        return self.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                profile_id=profile_id,

                version=latest_version.version,

                parameter_values=None,
            )
        )

    def can_instantiate(

        self,

        profile_id,

    ) -> bool:
        """
        Check whether a profile ID can currently be instantiated.

        Args:
            profile_id: The profile ID to check

        Returns:
            True if the profile can be resolved and has at least one
            published version, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError:
                If the profile ID is None or blank
        """

        self._validate_profile_id(
            profile_id
        )

        if not self._resolver.can_resolve(profile_id):

            return False

        return self._version_service.latest(profile_id) is not None

    def preview(

        self,

        profile_id,

        version,

    ) -> bool:
        """
        Check whether a specific published version of a profile
        could be instantiated, without creating an instance.

        Args:
            profile_id: The profile ID to check
            version: The version identifier to check

        Returns:
            True if the profile can be resolved and the version has
            been published for it, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError:
                If the profile ID or version is None or blank
        """

        self._validate_profile_id(
            profile_id
        )

        self._validate_version(
            version
        )

        if not self._resolver.can_resolve(profile_id):

            return False

        return self._version_service.find(

            profile_id,

            version,
        ) is not None

    def _validate_profile_id(

        self,

        profile_id,

    ) -> None:

        if (

            profile_id is None

            or not profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance with an empty or "
                    "blank profile ID."
                )
            )

    def _validate_version(

        self,

        version,

    ) -> None:

        if (

            version is None

            or not version.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance with an empty or "
                    "blank version."
                )
            )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance from a None "
                    "request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance: request must be "
                    "a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest."
                )
            )

        self._validate_profile_id(
            request.profile_id
        )

        self._validate_version(
            request.version
        )

        if (

            request.parameter_values is not None

            and not isinstance(

                request.parameter_values,

                Mapping,
            )
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError(
                    "Cannot instantiate a profile instance: parameter "
                    "values must be a mapping or None."
                )
            )
