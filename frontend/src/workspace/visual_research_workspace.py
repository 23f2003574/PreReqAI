from .research_workspace import (
    ResearchWorkspace,
)

from .workspace_view import (
    WorkspaceView,
)


class VisualResearchWorkspace:
    """
    High-level visual research experience
    coordinating exploration, interaction,
    and contextual learning.
    """

    def __init__(

        self,

        correlation_provider=None,

    ):

        self.workspace = (

            ResearchWorkspace(

                correlation_provider=(
                    correlation_provider
                )
            )
        )

    @property
    def state(self):

        return self.workspace.state

    def open_paper(

        self,

        paper_title: str,

        sections,

        knowledge_graph=None,

        session=None,

    ):

        outline = (

            self.workspace
            .load_paper_outline(

                paper_title,

                sections,
            )
        )

        graph = None

        if knowledge_graph is not None:

            graph = (

                self.workspace
                .load_knowledge_graph(

                    knowledge_graph
                )
            )

        if session is not None:

            self.workspace.state.active_session = (
                session
            )

            if hasattr(

                session,

                "interaction_history",
            ):

                self.workspace.load_interaction_history(

                    session
                )

        return {

            "outline": outline,

            "knowledge_graph": graph,

            "session": session,
        }

    def explore_section(

        self,

        node,

    ):

        return (

            self.workspace
            .select_outline_node(

                node
            )
        )

    def explore_graph_node(

        self,

        node_id: str,

    ):

        return (

            self.workspace
            .select_graph_node(

                node_id
            )
        )

    def inspect_object(

        self,

        research_object,

    ):

        return (

            self.workspace
            .select_object(

                research_object
            )
        )

    def available_actions(self):

        return (

            self.workspace
            .available_actions()
        )

    def perform_action(

        self,

        action,

        session=None,

    ):

        active_session = (

            session

            if session is not None

            else self.state.active_session
        )

        if active_session is None:

            raise ValueError(

                "An active research session "
                "is required to execute "
                "educational actions."
            )

        return (

            self.workspace
            .execute_action(

                active_session,

                action,
            )
        )

    def recommendations(self):

        return (

            self.workspace
            .next_action_recommendations()
        )

    def history(self):

        return (

            self.workspace
            .interaction_history_entries()
        )

    def timeline(self):

        return (

            self.workspace
            .workflow_timeline_steps()
        )

    def learning_content(self):

        return (

            self.workspace
            .active_learning_content()
        )

    def restore_learning_artifact(

        self,

        artifact,

    ):

        return (

            self.workspace
            .restore_learning_artifact(

                artifact
            )
        )

    def breadcrumbs(self):

        return (

            self.workspace
            .breadcrumb_items()
        )

    def switch_view(

        self,

        view: WorkspaceView | str,

    ):

        value = (

            view.value

            if isinstance(

                view,

                WorkspaceView,
            )

            else view
        )

        self.workspace.set_active_view(
            value
        )

        return self.state.active_view

    def snapshot(self):

        return {

            "active_paper":
                self.state.active_paper,

            "active_session":
                self.state.active_session,

            "selected_object":
                self.state.selected_object,

            "active_view":
                self.state.active_view,

            "breadcrumbs":
                self.breadcrumbs(),

            "timeline":
                self.timeline(),

            "learning_content":
                self.learning_content(),

            "history":
                self.history(),

            "recommendations":
                self.recommendations(),
        }
