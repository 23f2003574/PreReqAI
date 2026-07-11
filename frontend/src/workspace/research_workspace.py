from .workspace_region import (
    WorkspaceRegion,
)

from .workspace_state import (
    WorkspaceState,
)

from .default_panels import (
    DEFAULT_WORKSPACE_PANELS,
)

from .workspace_panel_registry import (
    WorkspacePanelRegistry,
)

from frontend.src.inspector import (
    ResearchObjectInspector,
)

from backend.engine import (
    InteractiveResearchEngine,
)

from frontend.src.actions import (
    ObjectActionMenu,
    WorkspaceActionResult,
)

from frontend.src.explorer import (
    PaperOutlineExplorer,
)

from frontend.src.graph import (
    KnowledgeGraphWorkspaceView,
)


class ResearchWorkspace:
    """
    Coordinates the visual research
    workspace and its active state.
    """

    def __init__(self):

        self.state = (
            WorkspaceState()
        )

        self.regions = [

            WorkspaceRegion.HEADER,

            WorkspaceRegion.EXPLORER,

            WorkspaceRegion.MAIN,

            WorkspaceRegion.INSPECTOR,

            WorkspaceRegion.TIMELINE,
        ]

        self.panel_registry = (
            WorkspacePanelRegistry()
        )

        for panel in DEFAULT_WORKSPACE_PANELS:

            self.panel_registry.register(
                panel
            )

        self.object_inspector = (
            ResearchObjectInspector()
        )

        self.inspector_view = None

        self.interaction_engine = (
            InteractiveResearchEngine()
        )

        self.action_menu = (

            ObjectActionMenu(

                self.interaction_engine
            )
        )

        self.active_action_result = None

        self.paper_explorer = (
            PaperOutlineExplorer()
        )

        self.paper_outline = None

        self.knowledge_graph_view = (
            KnowledgeGraphWorkspaceView()
        )

        self.graph_view_model = None

    def panels_for(

        self,

        region: WorkspaceRegion,

    ):

        return (

            self.panel_registry.for_region(

                region
            )
        )

    def select_object(

        self,

        research_object,

    ):

        self.state.selected_object = (
            research_object
        )

        self.inspector_view = (

            self.object_inspector.inspect(

                research_object
            )
        )

        return self.inspector_view

    def available_actions(self):

        if (

            self.state.selected_object

            is None
        ):

            return []

        return self.action_menu.build(

            self.state.selected_object
        )

    def execute_action(

        self,

        session,

        action,

    ):

        research_object = (

            self.state.selected_object
        )

        if research_object is None:

            raise ValueError(

                "No research object "
                "is currently selected."
            )

        response = (

            self.action_menu.execute(

                session,

                research_object,

                action,
            )
        )

        result = WorkspaceActionResult(

            object_id=(
                research_object.id
            ),

            action=action.value,

            response=response,
        )

        self.active_action_result = result

        return result

    def set_active_view(

        self,

        view: str,

    ):

        self.state.active_view = view

    def set_active_region(

        self,

        region: WorkspaceRegion,

    ):

        self.state.active_region = (
            region.value
        )

    def load_paper_outline(

        self,

        paper_title: str,

        sections,

    ):

        self.paper_outline = (

            self.paper_explorer.build(

                paper_title,

                sections,
            )
        )

        return self.paper_outline

    def select_outline_node(

        self,

        node,

    ):

        section = (

            self.paper_explorer.select(

                node
            )
        )

        self.state.metadata[

            "selected_section"

        ] = section

        return section

    def load_knowledge_graph(

        self,

        knowledge_graph,

    ):

        self.graph_view_model = (

            self.knowledge_graph_view.build(

                knowledge_graph
            )
        )

        return self.graph_view_model

    def select_graph_node(

        self,

        node_id: str,

    ):

        node = (

            self.knowledge_graph_view

            .select_node(

                node_id
            )
        )

        if node is None:

            return None

        self.state.metadata[

            "selected_graph_node"

        ] = node

        return node

    def show_knowledge_graph(self):

        self.set_active_view(

            "knowledge_graph"
        )

    def show_paper(self):

        self.set_active_view(

            "paper"
        )
