from frontend.src.workspace import (

    WorkspacePanel,

    WorkspacePanelRegistry,

    WorkspaceRegion,
)


def test_panel_registration():

    registry = (
        WorkspacePanelRegistry()
    )

    panel = WorkspacePanel(

        id="knowledge-graph",

        title="Knowledge Graph",

        region=WorkspaceRegion.MAIN,

        component="KnowledgeGraphView",
    )

    registry.register(
        panel
    )

    assert (

        registry.get(
            "knowledge-graph"
        )

        == panel
    )


def test_panels_for_region():

    registry = (
        WorkspacePanelRegistry()
    )

    panel = WorkspacePanel(

        id="paper-explorer",

        title="Paper Explorer",

        region=WorkspaceRegion.EXPLORER,

        component="PaperExplorer",
    )

    registry.register(
        panel
    )

    panels = registry.for_region(

        WorkspaceRegion.EXPLORER
    )

    assert panel in panels
