from .research_session_comparison import (
    ResearchSessionComparison,
)

from .research_state_change import (
    ResearchStateChange,
)

from .research_state_change_type import (
    ResearchStateChangeType,
)


class ResearchSessionComparator:
    """
    Compares meaningful fields between
    current and target research session
    snapshots.
    """

    DEFAULT_FIELDS = (

        "paper_id",

        "paper_title",

        "selected_section_id",

        "selected_object_id",

        "selected_graph_node_id",

        "active_workflow_step_id",

        "artifact_ids",
    )

    def __init__(

        self,

        fields=None,

    ):

        self.fields = tuple(

            fields

            or self.DEFAULT_FIELDS
        )

    def compare(

        self,

        current_snapshot,

        target_snapshot,

    ) -> ResearchSessionComparison:

        changes = []

        for field_name in self.fields:

            current_value = (

                self._resolve_field(

                    current_snapshot,

                    field_name,
                )
            )

            target_value = (

                self._resolve_field(

                    target_snapshot,

                    field_name,
                )
            )

            if (

                current_value

                == target_value
            ):

                continue

            if (

                isinstance(
                    current_value,
                    list,
                )

                and

                isinstance(
                    target_value,
                    list,
                )
            ):

                changes.append(

                    self._compare_list(

                        field_name,

                        current_value,

                        target_value,
                    )
                )

                continue

            change_type = (

                self._change_type(

                    current_value,

                    target_value,
                )
            )

            changes.append(

                ResearchStateChange(

                    field=field_name,

                    change_type=(
                        change_type
                    ),

                    current_value=(
                        current_value
                    ),

                    target_value=(
                        target_value
                    ),
                )
            )

        return ResearchSessionComparison(

            changes=changes
        )

    @staticmethod
    def _resolve_field(

        snapshot,

        field_name: str,

    ):

        if (

            field_name

            == "active_workflow_step_id"
        ):

            return (

                ResearchSessionComparator
                ._active_workflow_step_id(

                    snapshot
                )
            )

        return getattr(

            snapshot,

            field_name,

            None,
        )

    @staticmethod
    def _active_workflow_step_id(

        snapshot,

    ):

        for step in snapshot.timeline:

            if (

                step.get("status")

                == "active"
            ):

                return step.get(
                    "id"
                )

        return None

    def _compare_list(

        self,

        field_name: str,

        current_value: list,

        target_value: list,

    ):

        added_values = [

            value

            for value

            in target_value

            if value not in current_value
        ]

        removed_values = [

            value

            for value

            in current_value

            if value not in target_value
        ]

        return ResearchStateChange(

            field=field_name,

            change_type=(

                ResearchStateChangeType
                .CHANGED
            ),

            current_value=(
                current_value
            ),

            target_value=(
                target_value
            ),

            added_values=(
                added_values
            ),

            removed_values=(
                removed_values
            ),
        )

    def _change_type(

        self,

        current_value,

        target_value,

    ):

        if (

            current_value is None

            and

            target_value is not None
        ):

            return (

                ResearchStateChangeType
                .ADDED
            )

        if (

            current_value is not None

            and

            target_value is None
        ):

            return (

                ResearchStateChangeType
                .REMOVED
            )

        return (

            ResearchStateChangeType
            .CHANGED
        )
