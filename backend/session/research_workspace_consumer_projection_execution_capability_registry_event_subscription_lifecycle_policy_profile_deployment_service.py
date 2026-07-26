from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentService:
    """
    Deploys a validated, compatible consumer projection execution
    capability registry event subscription lifecycle policy profile
    version into a target runtime environment: resolve the profile,
    resolve the requested (or current) version, validate it, verify
    its compatibility, and publish a fresh profile instance.

    The service's responsibility is orchestrating deployment, not
    profile registration, versioning, validation rules, or
    compatibility rule evaluation themselves. It does NOT register
    profiles, publish versions, mutate a registry or version
    history, persist results, log, or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping is guarded by an
      internal lock
    - Conflict-aware: deploy() rejects a (profile ID, target
      environment) pair that already has an active deployment;
      deploy_or_replace() does not
    - Side-effect free on its inputs: Never mutates the resolved
      profile, registry, or version history
    """

    def __init__(

        self,

        resolver,

        version_service,

        validator,

        compatibility_service,

    ):
        """
        Args:
            resolver: The profile resolver used to resolve a profile
                ID. Any object exposing `resolve_or_raise(profile_id)`
                and `can_resolve(profile_id)` is accepted
            version_service: The version service used to resolve a
                profile's published versions. Any object exposing
                `find(profile_id, version)` and `latest(profile_id)`
                is accepted
            validator: The validator used to validate a resolved
                version before deployment. Any object exposing
                `validate_version(version)` is accepted
            compatibility_service: The compatibility service used to
                verify a version's compatibility before deployment.
                Any object exposing `check_version(profile_id,
                version)` is accepted
        """

        self._resolver = resolver

        self._version_service = version_service

        self._validator = validator

        self._compatibility_service = compatibility_service

        self._active_deployments = {}

        self._lock = RLock()

    def deploy(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult:
        """
        Deploy a profile version into its target environment.

        Args:
            request: The deployment request naming the profile,
                version, and target environment

        Returns:
            An immutable deployment result carrying the newly
            published profile instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError:
                If the request is malformed, the profile or version
                cannot be resolved, the version fails validation or
                compatibility verification, or the profile already
                has an active deployment in the target environment
        """

        return self._deploy(

            request,

            allow_redeploy=False,
        )

    def deploy_or_replace(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult:
        """
        Deploy a profile version into its target environment,
        replacing any deployment already active for the same profile
        and target environment rather than rejecting it as a
        conflict.

        Args:
            request: The deployment request naming the profile,
                version, and target environment

        Returns:
            An immutable deployment result carrying the newly
            published profile instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError:
                If the request is malformed, the profile or version
                cannot be resolved, or the version fails validation
                or compatibility verification
        """

        return self._deploy(

            request,

            allow_redeploy=True,
        )

    def can_deploy(

        self,

        profile_id,

        version,

        target_environment,

    ) -> bool:
        """
        Check whether deploy() would currently succeed for a profile,
        version, and target environment.

        Args:
            profile_id: The profile to check
            version: The version to check, or None to check the
                profile's current version
            target_environment: The target environment to check

        Returns:
            True if the profile and version resolve, the version is
            valid and compatible, and no deployment is already
            active for the profile and target environment, False
            otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError:
                If the profile ID or target environment is None or
                blank, or version is not None and is blank
        """

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        self._validate_identifier(
            target_environment,

            "target environment",
        )

        if version is not None:

            self._validate_identifier(
                version,

                "version",
            )

        with self._lock:

            if (

                profile_id,

                target_environment,

            ) in self._active_deployments:

                return False

        if not self._resolver.can_resolve(profile_id):

            return False

        version_object = self._resolve_version(

            profile_id,

            version,
        )

        if version_object is None:

            return False

        if not self._validator.validate_version(
            version_object
        ).valid:

            return False

        return self._compatibility_service.check_version(

            profile_id,

            version_object.version,
        ).compatible

    def _deploy(

        self,

        request,

        allow_redeploy,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult:

        self._validate_request(
            request
        )

        key = (

            request.profile_id,

            request.target_environment,
        )

        with self._lock:

            if (

                not allow_redeploy

                and key in self._active_deployments
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                        "Cannot deploy: profile ID "
                        f"{request.profile_id!r} already has an active "
                        f"deployment in target environment "
                        f"{request.target_environment!r}."
                    )
                )

            try:

                self._resolver.resolve_or_raise(
                    request.profile_id
                )

            except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError as error:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                        "Cannot deploy: no profile was found under profile "
                        f"ID {request.profile_id!r}."
                    )
                ) from error

            version_object = self._resolve_version(

                request.profile_id,

                request.version,
            )

            if version_object is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                        "Cannot deploy: no version was found for profile ID "
                        f"{request.profile_id!r}."
                        if request.version is None
                        else
                        f"Cannot deploy: version {request.version!r} was "
                        f"not found for profile ID {request.profile_id!r}."
                    )
                )

            validation = self._validator.validate_version(
                version_object
            )

            if not validation.valid:

                violation_codes = ", ".join(

                    violation.code

                    for violation

                    in validation.violations
                )

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                        f"Cannot deploy version {version_object.version!r}: "
                        f"failed validation: {violation_codes}."
                    )
                )

            compatibility_result = self._compatibility_service.check_version(

                request.profile_id,

                version_object.version,
            )

            if not compatibility_result.compatible:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                        f"Cannot deploy version {version_object.version!r}: "
                        "failed compatibility verification."
                    )
                )

            resolved_parameter_values = (
                request.parameter_values
                if request.parameter_values is not None
                else {}
            )

            deployed_profile = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
                    profile_id=request.profile_id,

                    version=version_object.version,

                    policy_identifiers=tuple(
                        version_object.policy_identifiers
                    ),

                    parameter_values=MappingProxyType(
                        dict(
                            resolved_parameter_values
                        )
                    ),
                )
            )

            deployment_id = self._generate_deployment_id(

                request.profile_id,

                request.target_environment,
            )

            self._active_deployments[key] = deployment_id

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult(
                    deployment_id=deployment_id,

                    deployed_profile=deployed_profile,

                    target_environment=request.target_environment,

                    deployed_at=datetime.now(
                        timezone.utc
                    ),

                    successful=True,
                )
            )

    def _resolve_version(

        self,

        profile_id,

        version,

    ):

        if version is None:

            return self._version_service.latest(
                profile_id
            )

        return self._version_service.find(

            profile_id,

            version,
        )

    def _generate_deployment_id(

        self,

        profile_id,

        target_environment,

    ) -> str:

        return f"{profile_id}::{target_environment}"

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                    f"Cannot deploy with an empty or blank {label}."
                )
            )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                    "Cannot deploy from a None request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                    "Cannot deploy: request must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest."
                )
            )

        self._validate_identifier(
            request.profile_id,

            "profile ID",
        )

        self._validate_identifier(
            request.target_environment,

            "target environment",
        )

        if request.version is not None:

            self._validate_identifier(
                request.version,

                "version",
            )

        if (

            request.parameter_values is not None

            and not isinstance(

                request.parameter_values,

                Mapping,
            )
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError(
                    "Cannot deploy: parameter values must be a mapping or "
                    "None."
                )
            )
