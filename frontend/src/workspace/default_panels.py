from .workspace_panel import (
    WorkspacePanel,
)

from .workspace_region import (
    WorkspaceRegion,
)


DEFAULT_WORKSPACE_PANELS = [

    WorkspacePanel(

        id="navigation-breadcrumbs",

        title="Navigation Breadcrumbs",

        region=WorkspaceRegion.HEADER,

        component="NavigationBreadcrumbs",

        metadata={

            "interactive": True,

            "supports_backtracking": True,

            "contextual": True,
        },
    ),

    WorkspacePanel(

        id="paper-explorer",

        title="Paper Explorer",

        region=WorkspaceRegion.EXPLORER,

        component="PaperOutlineExplorer",

        metadata={

            "hierarchical": True,

            "supports_selection": True,

            "supports_expansion": True,
        },
    ),

    WorkspacePanel(

        id="paper-view",

        title="Paper View",

        region=WorkspaceRegion.MAIN,

        component="PaperView",
    ),

    WorkspacePanel(

        id="knowledge-graph",

        title="Knowledge Graph",

        region=WorkspaceRegion.MAIN,

        component="KnowledgeGraphWorkspaceView",

        visible=True,

        metadata={

            "interactive": True,

            "supports_selection": True,

            "supports_zoom": True,

            "supports_pan": True,
        },
    ),

    WorkspacePanel(

        id="object-inspector",

        title="Object Inspector",

        region=WorkspaceRegion.INSPECTOR,

        component="ResearchObjectInspector",

        metadata={

            "contextual": True,

            "requires_selection": True,
        },
    ),

    WorkspacePanel(

        id="learning-timeline",

        title="Learning Timeline",

        region=WorkspaceRegion.TIMELINE,

        component="LearningWorkflowTimeline",

        metadata={

            "interactive": True,

            "tracks_progress": True,

            "supports_failure": True,

            "supports_skipping": True,
        },
    ),
]
