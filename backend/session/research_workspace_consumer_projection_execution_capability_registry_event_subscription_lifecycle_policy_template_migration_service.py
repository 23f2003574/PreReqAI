from collections import (
    deque,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_migration_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_migration_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_migration_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService:
    """
    Plans and applies migrations of a consumer projection execution
    capability registry event subscription lifecycle policy between
    template versions, over a fixed graph of registered single-hop
    migration steps.

    The service's responsibility is path discovery and sequential
    application of migration steps, not template registration,
    versioning, resolution, or compatibility checking. It does NOT
    register templates, publish versions, resolve templates, check
    compatibility, persist results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed migration steps it was
      constructed with
    - Deterministic: Same source version, target version, and
      registered steps always produce the same plan
    - Side-effect free: Never mutates the lifecycle policy it
      migrates from
    """

    def __init__(

        self,

        steps=None,

    ):
        """
        Args:
            steps: A mapping of (source_version, target_version)
                pairs to single-hop transformations, or None for no
                known migrations

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError:
                If any step key is not a two-element tuple of
                non-blank version strings, or any step value is not
                callable
        """

        self._adjacency = self._build_adjacency(

            steps

            if steps is not None

            else {}
        )

    def plan(

        self,

        template,

        source_version,

        target_version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan:
        """
        Build an immutable migration plan from a source version to a
        target version.

        Args:
            template: The template the migration is being planned
                for
            source_version: The version to migrate from
            target_version: The version to migrate to

        Returns:
            An immutable migration plan carrying every migration
            step to apply, in order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError:
                If the template is None, either version is None or
                blank, the versions are identical, or no migration
                path connects them
        """

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    "Cannot plan a migration for a None template."
                )
            )

        self._validate_version(
            source_version,

            "source version",
        )

        self._validate_version(
            target_version,

            "target version",
        )

        if source_version == target_version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    "Cannot plan a migration: source version and target "
                    f"version are both {source_version!r}."
                )
            )

        path = self._find_path(

            source_version,

            target_version,
        )

        if path is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    "Cannot plan a migration: no migration path connects "
                    f"version {source_version!r} to version "
                    f"{target_version!r}."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan(
                source_version=source_version,

                target_version=target_version,

                migration_steps=tuple(
                    path
                ),
            )
        )

    def migrate(

        self,

        lifecycle_policy,

        migration_plan,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult:
        """
        Apply a migration plan's steps to a lifecycle policy,
        sequentially.

        Args:
            lifecycle_policy: The lifecycle policy to migrate. It is
                never modified
            migration_plan: The plan describing which steps to apply

        Returns:
            An immutable migration result carrying a new, migrated
            lifecycle policy instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError:
                If the lifecycle policy or migration plan is None,
                or a migration step is not callable or does not
                produce a lifecycle policy
        """

        if lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    "Cannot migrate a None lifecycle policy."
                )
            )

        if migration_plan is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    "Cannot migrate with a None migration plan."
                )
            )

        current = lifecycle_policy

        for step in migration_plan.migration_steps:

            if not callable(step):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                        "Cannot migrate: migration step is not callable."
                    )
                )

            current = step(
                current
            )

            if not isinstance(

                current,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                        "Cannot migrate: a migration step did not produce a "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult(
                migrated_policy=current,

                source_version=migration_plan.source_version,

                target_version=migration_plan.target_version,

                migration_successful=True,
            )
        )

    def can_migrate(

        self,

        source_version,

        target_version,

    ) -> bool:
        """
        Check whether a migration path connects a source version to
        a target version.

        Args:
            source_version: The version to migrate from
            target_version: The version to migrate to

        Returns:
            True if a migration path connects the two distinct
            versions, False otherwise, including when the versions
            are identical

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError:
                If either version is None or blank
        """

        self._validate_version(
            source_version,

            "source version",
        )

        self._validate_version(
            target_version,

            "target version",
        )

        if source_version == target_version:

            return False

        return self._find_path(

            source_version,

            target_version,
        ) is not None

    def _find_path(

        self,

        source_version,

        target_version,

    ):

        visited = {source_version}

        queue = deque(
            [
                (
                    source_version,

                    [],
                )
            ]
        )

        while queue:

            current_version, path_so_far = queue.popleft()

            for next_version, transform in self._adjacency.get(

                current_version,

                (),
            ):

                if next_version in visited:

                    continue

                next_path = path_so_far + [
                    transform
                ]

                if next_version == target_version:

                    return next_path

                visited.add(
                    next_version
                )

                queue.append(
                    (
                        next_version,

                        next_path,
                    )
                )

        return None

    def _validate_version(

        self,

        version,

        label,

    ) -> None:

        if (

            version is None

            or not version.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                    f"Cannot operate with an empty or blank {label}."
                )
            )

    def _build_adjacency(

        self,

        steps,

    ) -> dict:

        entries = (

            steps.items()

            if hasattr(steps, "items")

            else steps
        )

        adjacency = {}

        for key, transform in entries:

            if (

                not isinstance(key, tuple)

                or len(key) != 2
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                        "Cannot build a migration service: migration step "
                        "key must be a (source_version, target_version) "
                        "pair."
                    )
                )

            step_source, step_target = key

            self._validate_version(
                step_source,

                "migration step source version",
            )

            self._validate_version(
                step_target,

                "migration step target version",
            )

            if not callable(transform):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError(
                        "Cannot build a migration service: migration step "
                        f"from {step_source!r} to {step_target!r} is not "
                        "callable."
                    )
                )

            adjacency.setdefault(
                step_source,

                [],
            ).append(
                (
                    step_target,

                    transform,
                )
            )

        return adjacency
