from .workspace_panel import (
    WorkspacePanel,
)

from .workspace_region import (
    WorkspaceRegion,
)


DEFAULT_WORKSPACE_PANELS = [

    WorkspacePanel(

        id="paper-explorer",

        title="Paper Explorer",

        region=WorkspaceRegion.EXPLORER,

        component="PaperExplorer",
    ),

    WorkspacePanel(

        id="paper-view",

        title="Paper View",

        region=WorkspaceRegion.MAIN,

        component="PaperView",
    ),

    WorkspacePanel(

        id="object-inspector",

        title="Object Inspector",

        region=WorkspaceRegion.INSPECTOR,

        component="ResearchObjectInspector",
    ),

    WorkspacePanel(

        id="learning-timeline",

        title="Learning Timeline",

        region=WorkspaceRegion.TIMELINE,

        component="LearningTimeline",
    ),
]
