from .research_workspace_consumer_projection_execution_capability_registry_merge_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner:
    """
    Compares a base and an incoming consumer projection execution
    capability registry snapshot and produces a deterministic merge
    plan, without performing the merge.

    The planner's responsibility is planning, not execution. It
    does NOT mutate either snapshot, mutate any decision package,
    resolve conflicts, or publish events - it only describes what a
    later merge would do.

    The planner is:
    - Stateless: No instance state
    - Deterministic: Same pair of snapshots always produces the
      same plan
    - Side-effect free: Never mutates its inputs
    """

    def plan(

        self,

        base,

        incoming,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan:
        """
        Compare a base and an incoming registry snapshot and
        produce the merge plan between them.

        Args:
            base: The existing registry snapshot
            incoming: The registry snapshot to be merged onto base

        Returns:
            An immutable merge plan describing which projections
            would be added, updated, or left unchanged
        """

        base_by_name = {

            package.projection_name:
                package

            for package

            in base.packages
        }

        incoming_by_name = {

            package.projection_name:
                package

            for package

            in incoming.packages
        }

        addition_names = (

            incoming_by_name.keys()

            - base_by_name.keys()
        )

        common_names = (

            base_by_name.keys()

            & incoming_by_name.keys()
        )

        update_names = {

            name

            for name

            in common_names

            if (

                base_by_name[name]

                != incoming_by_name[name]
            )
        }

        unchanged_names = (

            common_names

            - update_names
        )

        additions = tuple(

            incoming_by_name[name]

            for name

            in sorted(
                addition_names
            )
        )

        updates = tuple(

            incoming_by_name[name]

            for name

            in sorted(
                update_names
            )
        )

        unchanged = tuple(

            incoming_by_name[name]

            for name

            in sorted(
                unchanged_names
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan(

                additions=additions,

                updates=updates,

                unchanged=unchanged,
            )
        )
