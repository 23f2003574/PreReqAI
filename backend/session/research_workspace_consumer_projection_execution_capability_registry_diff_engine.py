from .research_workspace_consumer_projection_execution_capability_registry_diff import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiff,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine:
    """
    Compares two consumer projection execution capability registry
    snapshots and produces a deterministic change set for
    downstream synchronization and diagnostics.

    The engine's responsibility is comparison, not merging. It does
    NOT mutate either snapshot, mutate any decision package, or
    publish events - it only produces a new diff object.

    The engine is:
    - Stateless: No instance state
    - Deterministic: Same pair of snapshots always produces the
      same diff
    - Side-effect free: Never mutates its inputs
    """

    def diff(

        self,

        previous,

        current,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiff:
        """
        Compare two registry snapshots and produce the change set
        between them.

        Args:
            previous: The earlier registry snapshot
            current: The later registry snapshot

        Returns:
            An immutable diff describing which projections were
            added, removed, or modified between the two snapshots
        """

        previous_by_name = {

            package.projection_name:
                package

            for package

            in previous.packages
        }

        current_by_name = {

            package.projection_name:
                package

            for package

            in current.packages
        }

        added_names = (

            current_by_name.keys()

            - previous_by_name.keys()
        )

        removed_names = (

            previous_by_name.keys()

            - current_by_name.keys()
        )

        common_names = (

            previous_by_name.keys()

            & current_by_name.keys()
        )

        modified_names = {

            name

            for name

            in common_names

            if (

                previous_by_name[name]

                != current_by_name[name]
            )
        }

        added = tuple(

            current_by_name[name]

            for name

            in sorted(
                added_names
            )
        )

        removed = tuple(

            previous_by_name[name]

            for name

            in sorted(
                removed_names
            )
        )

        modified = tuple(

            current_by_name[name]

            for name

            in sorted(
                modified_names
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiff(

                added=added,

                removed=removed,

                modified=modified,
            )
        )
