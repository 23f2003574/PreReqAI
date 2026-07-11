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

from frontend.src.navigation import (
    NavigationBreadcrumbs,
)

from frontend.src.timeline import (
    LearningWorkflowTimeline,
)

from frontend.src.learning import (
    ContextualLearningPanel,
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

        self.breadcrumbs = (
            NavigationBreadcrumbs()
        )

        self.learning_timeline = (
            LearningWorkflowTimeline()
        )

        self.learning_panel = (
            ContextualLearningPanel()
        )

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

        self.breadcrumbs.enter(

            id=research_object.id,

            label=research_object.title,

            context_type=(

                research_object
                .object_type
                .value
            ),

            source=research_object,
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

        self.learning_panel.present_response(

            research_object,

            action,

            response,
        )

        self.show_learning_content()

        workflow_steps = (

            response.get(
                "workflow_steps"
            )

            if isinstance(
                response,
                dict,
            )

            else None
        )

        if workflow_steps:

            self.load_workflow_timeline(

                workflow_steps
            )

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

        self.breadcrumbs.trail.clear()

        self.breadcrumbs.enter(

            id="paper",

            label=paper_title,

            context_type="paper",

            source=self.paper_outline,
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

        self.breadcrumbs.enter(

            id=node.id,

            label=node.title,

            context_type="section",

            source=section,
        )

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

        self.breadcrumbs.enter(

            id=node.id,

            label=node.label,

            context_type=(

                f"graph_{node.node_type}"
            ),

            source=node,
        )

        return node

    def show_knowledge_graph(self):

        self.set_active_view(

            "knowledge_graph"
        )

    def show_paper(self):

        self.set_active_view(

            "paper"
        )

    def show_learning_content(self):

        self.set_active_view(

            "learning"
        )

    def navigate_breadcrumb(

        self,

        index: int,

    ):

        item = (

            self.breadcrumbs.navigate_to(

                index
            )
        )

        self.state.metadata[

            "navigation_context"

        ] = item

        return item

    def breadcrumb_items(self):

        return (

            self.breadcrumbs.items()
        )

    def load_workflow_timeline(

        self,

        workflow_steps,

    ):

        return (

            self.learning_timeline.load(

                workflow_steps
            )
        )

    def activate_workflow_step(

        self,

        step_id: str,

    ):

        return (

            self.learning_timeline.activate(

                step_id
            )
        )

    def complete_workflow_step(

        self,

        step_id: str,

    ):

        return (

            self.learning_timeline.complete(

                step_id
            )
        )

    def fail_workflow_step(

        self,

        step_id: str,

    ):

        return (

            self.learning_timeline.fail(

                step_id
            )
        )

    def skip_workflow_step(

        self,

        step_id: str,

    ):

        return (

            self.learning_timeline.skip(

                step_id
            )
        )

    def workflow_timeline_steps(self):

        return list(

            self.learning_timeline.steps
        )

    def active_learning_content(self):

        return (

            self.learning_panel
            .active_content
        )

    def learning_content_history(self):

        return list(

            self.learning_panel
            .content_history
        )
