from .workspace_region import (
    WorkspaceRegion,
)

from .workspace_state import (
    WorkspaceState,
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
