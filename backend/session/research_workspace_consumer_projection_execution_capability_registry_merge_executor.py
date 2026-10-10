from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_merge_execution_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_merge_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
)

from .research_workspace_consumer_projection_execution_capability_registry_merge_validator import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor:
    """
    Executes a validated consumer projection execution capability
    registry merge plan, producing a brand-new registry without
    mutating the original.

    The executor's responsibility is applying an already-planned
    set of changes, not resolving conflicts or persisting anything.
    It does NOT mutate the input registry, mutate the merge plan,
    or mutate any decision package.

    The executor is:
    - Stateless: No instance state
    - Deterministic: Same registry and merge plan always produce
      the same merged registry
    - Side-effect free: Never mutates its inputs
    """

    def execute(

        self,

        registry,

        plan,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry:
        """
        Apply a merge plan against a registry and return a new,
        merged registry.

        Args:
            registry: The existing registry the plan was computed
                against
            plan: The merge plan describing additions, updates, and
                unchanged entries

        Returns:
            A brand-new registry containing every unchanged entry,
            every addition, and every update

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError:
                If the registry or plan is None or the wrong type,
                or if the merge plan fails integrity validation
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
                    "Cannot execute a merge against a None "
                    "registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
                    "Cannot execute merge: registry must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry."
                )
            )

        if plan is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
                    "Cannot execute a None merge plan."
                )
            )

        if not isinstance(

            plan,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
                    "Cannot execute merge: plan must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan."
                )
            )

        validation_report = (

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
            .validate(
                plan
            )
        )

        if not validation_report.is_valid:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
                    "Cannot execute merge: plan is invalid "
                    "(duplicate or empty projection names: "
                    f"{validation_report.duplicate_projection_names})."
                )
            )

        merged_registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        )

        for projection_name in registry.list_projection_names():

            merged_registry.register(
                registry.get(
                    projection_name
                )
            )

        for package in plan.additions:

            merged_registry.register(
                package
            )

        for package in plan.updates:

            merged_registry.register(
                package
            )

        return merged_registry
