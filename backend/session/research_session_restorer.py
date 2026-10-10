from .research_session_restoration_result import (
    ResearchSessionRestorationResult,
)


class ResearchSessionRestorer:
    """
    Restores persisted research session
    state into a live visual workspace.
    """

    def __init__(

        self,

        resolver,

    ):

        self.resolver = resolver

    def restore(

        self,

        snapshot,

        workspace,

    ):

        unresolved = []

        restored_object = (

            self.resolver.resolve_object(

                snapshot.selected_object_id
            )
        )

        restored_section = (

            self.resolver.resolve_section(

                snapshot.selected_section_id
            )
        )

        restored_graph_node = (

            self.resolver.resolve_graph_node(

                snapshot
                .selected_graph_node_id
            )
        )

        self._track_unresolved(

            unresolved,

            "research_object",

            snapshot.selected_object_id,

            restored_object,
        )

        self._track_unresolved(

            unresolved,

            "section",

            snapshot.selected_section_id,

            restored_section,
        )

        self._track_unresolved(

            unresolved,

            "graph_node",

            snapshot
            .selected_graph_node_id,

            restored_graph_node,
        )

        self._restore_view(

            snapshot,

            workspace,
        )

        self._restore_breadcrumbs(

            snapshot,

            workspace,
        )

        self._restore_timeline(

            snapshot,

            workspace,
        )

        self._restore_recommendations(

            snapshot,

            workspace,
        )

        if restored_section is not None:

            workspace.workspace.state.metadata[

                "selected_section"

            ] = restored_section

        if restored_graph_node is not None:

            workspace.workspace.state.metadata[

                "selected_graph_node"

            ] = restored_graph_node

        if restored_object is not None:

            workspace.workspace.state.selected_object = (
                restored_object
            )

        return (

            ResearchSessionRestorationResult(

                session_id=(
                    snapshot.session_id
                ),

                restored=True,

                restored_object=(
                    restored_object
                ),

                restored_section=(
                    restored_section
                ),

                restored_graph_node=(
                    restored_graph_node
                ),

                unresolved_references=(
                    unresolved
                ),
            )
        )

    def restore_snapshot(

        self,

        snapshot,

        workspace,

    ):

        self.restore(

            snapshot,

            workspace,
        )

        return workspace

    @staticmethod
    def _restore_view(

        snapshot,

        workspace,

    ):

        workspace.switch_view(

            snapshot.active_view
        )

    @staticmethod
    def _restore_breadcrumbs(

        snapshot,

        workspace,

    ):

        from frontend.src.navigation import (
            BreadcrumbItem,
        )

        trail = (

            workspace.workspace
            .breadcrumbs
            .trail
        )

        trail.clear()

        for item in snapshot.breadcrumbs:

            trail.push(

                BreadcrumbItem(

                    id=item["id"],

                    label=item["label"],

                    context_type=(

                        item[
                            "context_type"
                        ]
                    ),
                )
            )

    @staticmethod
    def _restore_timeline(

        snapshot,

        workspace,

    ):

        from frontend.src.timeline import (
            TimelineStep,
            TimelineStepStatus,
        )

        timeline = (

            workspace.workspace
            .learning_timeline
        )

        timeline.steps = [

            TimelineStep(

                id=item["id"],

                title=item["title"],

                status=(

                    TimelineStepStatus(

                        item["status"]
                    )
                ),
            )

            for item

            in snapshot.timeline
        ]

        active = next(

            (

                step.id

                for step

                in timeline.steps

                if (

                    step.status

                    == (
                        TimelineStepStatus
                        .ACTIVE
                    )
                )
            ),

            None,
        )

        timeline.active_step_id = (
            active
        )

    @staticmethod
    def _restore_recommendations(

        snapshot,

        workspace,

    ):

        from frontend.src.recommendations import (
            NextActionRecommendation,
        )

        recommendations = [

            NextActionRecommendation(

                id=item["id"],

                title=item["title"],

                description=(

                    item[
                        "description"
                    ]
                ),

                action=item["action"],

                object_id=(

                    item.get(
                        "object_id"
                    )
                ),

                priority=(

                    item.get(
                        "priority",

                        0,
                    )
                ),
            )

            for item

            in snapshot.recommendations
        ]

        workspace.workspace.load_recommendations(

            recommendations
        )

    @staticmethod
    def _track_unresolved(

        unresolved,

        reference_type: str,

        reference_id: str | None,

        resolved,

    ):

        if (

            reference_id is not None

            and resolved is None
        ):

            unresolved.append(

                f"{reference_type}:"
                f"{reference_id}"
            )
