from .research_workspace_consumer_projection_execution_capability_registry_merge_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
)

from .research_workspace_consumer_projection_execution_capability_registry_merge_validation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_merge_validation_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationReport,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator:
    """
    Inspects a consumer projection execution capability registry
    merge plan for integrity before it is handed to a future merge
    executor.

    The validator's responsibility is inspection, not repair. It
    does NOT modify the merge plan, move packages, repair
    duplicates, or remove invalid entries.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same merge plan always produces the same
      report
    - Side-effect free: Never mutates the merge plan or its
      packages
    """

    def validate(

        self,

        plan,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationReport:
        """
        Validate the integrity of a consumer projection execution
        capability registry merge plan.

        Args:
            plan: The merge plan to validate

        Returns:
            An immutable merge validation report summarizing the
            plan's collection sizes and any unsafe projection names

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError:
                If the plan is None, is not a merge plan, or
                contains an entry that cannot be inspected
        """

        if plan is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError(
                    "Cannot validate a None merge plan."
                )
            )

        if not isinstance(

            plan,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError(
                    "Cannot validate merge plan: plan must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan."
                )
            )

        all_names = []

        for collection in (

            plan.additions,

            plan.updates,

            plan.unchanged,
        ):

            for package in collection:

                try:

                    projection_name = (
                        package.projection_name
                    )

                except AttributeError as error:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError(
                            "Cannot validate merge plan: an entry "
                            "cannot be inspected as an execution "
                            f"capability decision package ({error})."
                        )
                    ) from error

                all_names.append(
                    projection_name
                )

        name_counts = {}

        for name in all_names:

            name_counts[name] = (

                name_counts.get(
                    name,

                    0,
                )

                + 1
            )

        duplicate_names = {

            name

            for name, count

            in name_counts.items()

            if count > 1
        }

        empty_names = {

            name

            for name

            in all_names

            if not name
        }

        problematic_names = tuple(

            sorted(

                duplicate_names

                | empty_names
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationReport(

                additions=len(
                    plan.additions
                ),

                updates=len(
                    plan.updates
                ),

                unchanged=len(
                    plan.unchanged
                ),

                duplicate_projection_names=problematic_names,

                is_valid=(
                    len(problematic_names) == 0
                ),
            )
        )
