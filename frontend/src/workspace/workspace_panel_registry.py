from .workspace_panel import (
    WorkspacePanel,
)

from .workspace_region import (
    WorkspaceRegion,
)


class WorkspacePanelRegistry:
    """
    Registers and manages modular
    panels inside the research workspace.
    """

    def __init__(self):

        self._panels: dict[
            str,
            WorkspacePanel,
        ] = {}

    def register(

        self,

        panel: WorkspacePanel,

    ):

        self._panels[
            panel.id
        ] = panel

    def unregister(

        self,

        panel_id: str,

    ):

        return self._panels.pop(

            panel_id,

            None,
        )

    def get(

        self,

        panel_id: str,

    ):

        return self._panels.get(
            panel_id,
        )

    def all(self):

        return list(
            self._panels.values()
        )

    def for_region(

        self,

        region: WorkspaceRegion,

    ):

        return [

            panel

            for panel

            in self._panels.values()

            if (

                panel.region == region

                and panel.visible
            )
        ]
