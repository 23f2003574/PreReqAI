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
