from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_migration_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_migration_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_migration_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationService:
    """
    Plans and applies migrations of a consumer projection execution
    capability registry event subscription lifecycle policy profile
    between published versions, validating compatibility before
    migrating and preserving existing parameter values whenever
    possible.

    The service's responsibility is path discovery and sequential
    application of migration steps, not profile registration,
    versioning, resolution, or compatibility rule evaluation itself.
    It does NOT register profiles, publish versions, mutate a
    registry or version history, persist results, log, or publish
    events.

    The service is:
    - Stateless: Holds only the fixed custom migration steps and
      lookup sources it was constructed with
    - Deterministic: Same profile ID, source version, target
      version, and registered steps always produce the same plan
    - Side-effect free: Never mutates the registry, version history,
      or any historical version it migrates from
    """

    def __init__(

        self,

        resolver,

        version_service,

        compatibility_service,

        steps=None,

    ):
        """
        Args:
            resolver: The profile resolver used to resolve a profile
                ID. Any object exposing `resolve_or_raise(profile_id)`
                and `can_resolve(profile_id)` is accepted
            version_service: The version service used to resolve a
                profile's published versions. Any object exposing
                `find(profile_id, version)` is accepted
            compatibility_service: The compatibility service used to
                validate a target version before migrating. Any
                object exposing `check_version(profile_id, version)`
                is accepted
            steps: A mapping of (source_version, target_version)
                pairs to custom single-hop profile instance
                transformations, or None to rely entirely on the
                service's default, parameter-preserving step

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError:
                If any step key is not a two-element tuple of
                non-blank version strings, any step value is not
                callable, or two steps share the same
                (source_version, target_version) key
        """

        self._resolver = resolver

        self._version_service = version_service

        self._compatibility_service = compatibility_service

        self._custom_steps = self._validated_steps(

            steps

            if steps is not None

            else {}
        )

    def plan(

        self,

        profile_id,

        source_version,

        target_version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan:
        """
        Build an immutable migration plan from a source version to a
        target version.

        Args:
            profile_id: The profile the migration is being planned
                for
            source_version: The version to migrate from
            target_version: The version to migrate to

        Returns:
            An immutable migration plan carrying every migration step
            to apply, in order. Empty when source_version and
            target_version are identical

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError:
                If the profile ID, source version, or target version
                is None or blank, the profile cannot be resolved,
                either version was not published for the profile, or
                the target version fails compatibility validation
        """

        _, target_version_object = self._resolve_context(

            profile_id,

            source_version,

            target_version,
        )

        migration_steps = self._build_migration_steps(

            profile_id,

            source_version,

            target_version,

            target_version_object,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan(
                profile_id=profile_id,

                source_version=source_version,

                target_version=target_version,

                migration_steps=migration_steps,
            )
        )

    def migrate(

        self,

        profile_id,

        source_version,

        target_version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult:
        """
        Migrate a profile from a source version to a target version.

        Args:
            profile_id: The profile to migrate
            source_version: The version to migrate from
            target_version: The version to migrate to

        Returns:
            An immutable migration result carrying a new, migrated
            profile instance. When source_version and target_version
            are identical, this is a no-op that carries the source
            version's own configuration forward unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError:
                If the profile ID, source version, or target version
                is None or blank, the profile cannot be resolved,
                either version was not published for the profile, or
                the target version fails compatibility validation
        """

        source_version_object, target_version_object = self._resolve_context(

            profile_id,

            source_version,

            target_version,
        )

        migration_steps = self._build_migration_steps(

            profile_id,

            source_version,

            target_version,

            target_version_object,
        )

        current = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
                profile_id=profile_id,

                version=source_version,

                policy_identifiers=tuple(
                    source_version_object.policy_identifiers
                ),

                parameter_values=MappingProxyType({}),
            )
        )

        for step in migration_steps:

            current = step(
                current
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult(
                source_version=source_version,

                target_version=target_version,

                migrated_profile=current,

                successful=True,
            )
        )

    def can_migrate(

        self,

        profile_id,

        source_version,

        target_version,

    ) -> bool:
        """
        Check whether a profile can be migrated from a source
        version to a target version.

        Args:
            profile_id: The profile to check
            source_version: The version to migrate from
            target_version: The version to migrate to

        Returns:
            True if the profile resolves, both versions have been
            published for it, and the target version is either
            identical to the source version or passes compatibility
            validation. False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError:
                If the profile ID, source version, or target version
                is None or blank
        """

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        self._validate_identifier(
            source_version,

            "source version",
        )

        self._validate_identifier(
            target_version,

            "target version",
        )

        if not self._resolver.can_resolve(profile_id):

            return False

        if self._version_service.find(profile_id, source_version) is None:

            return False

        if self._version_service.find(profile_id, target_version) is None:

            return False

        if source_version == target_version:

            return True

        return self._compatibility_service.check_version(

            profile_id,

            target_version,
        ).compatible

    def _resolve_context(

        self,

        profile_id,

        source_version,

        target_version,

    ) -> tuple:

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        self._validate_identifier(
            source_version,

            "source version",
        )

        self._validate_identifier(
            target_version,

            "target version",
        )

        try:

            self._resolver.resolve_or_raise(
                profile_id
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                    "Cannot plan a migration: no profile was found under "
                    f"profile ID {profile_id!r}."
                )
            ) from error

        source_version_object = self._version_service.find(

            profile_id,

            source_version,
        )

        if source_version_object is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                    f"Cannot plan a migration: source version {source_version!r} "
                    f"was not found for profile ID {profile_id!r}."
                )
            )

        target_version_object = self._version_service.find(

            profile_id,

            target_version,
        )

        if target_version_object is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                    f"Cannot plan a migration: target version {target_version!r} "
                    f"was not found for profile ID {profile_id!r}."
                )
            )

        return (

            source_version_object,

            target_version_object,
        )

    def _build_migration_steps(

        self,

        profile_id,

        source_version,

        target_version,

        target_version_object,

    ) -> tuple:

        if source_version == target_version:

            return ()

        compatibility_result = self._compatibility_service.check_version(

            profile_id,

            target_version,
        )

        if not compatibility_result.compatible:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                    "Cannot plan a migration: target version "
                    f"{target_version!r} failed compatibility validation."
                )
            )

        custom_step = self._custom_steps.get(
            (
                source_version,

                target_version,
            )
        )

        return (
            custom_step

            if custom_step is not None

            else self._default_step(
                target_version_object
            ),
        )

    def _default_step(

        self,

        target_version_object,

    ):

        def step(instance):

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
                    profile_id=instance.profile_id,

                    version=target_version_object.version,

                    policy_identifiers=tuple(
                        target_version_object.policy_identifiers
                    ),

                    parameter_values=instance.parameter_values,
                )
            )

        return step

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
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                    f"Cannot operate with an empty or blank {label}."
                )
            )

    def _validated_steps(

        self,

        steps,

    ) -> dict:

        entries = (

            steps.items()

            if hasattr(steps, "items")

            else steps
        )

        validated = {}

        for key, transform in entries:

            if (

                not isinstance(key, tuple)

                or len(key) != 2
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                        "Cannot build a migration service: migration step "
                        "key must be a (source_version, target_version) "
                        "pair."
                    )
                )

            step_source, step_target = key

            self._validate_identifier(
                step_source,

                "migration step source version",
            )

            self._validate_identifier(
                step_target,

                "migration step target version",
            )

            if not callable(transform):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                        "Cannot build a migration service: migration step "
                        f"from {step_source!r} to {step_target!r} is not "
                        "callable."
                    )
                )

            if key in validated:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError(
                        "Cannot build a migration service with duplicate "
                        f"migration step from {step_source!r} to "
                        f"{step_target!r}."
                    )
                )

            validated[key] = transform

        return validated
