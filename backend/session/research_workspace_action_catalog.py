from .research_workspace_action import (
    ResearchWorkspaceAction,
)

from .research_workspace_action_descriptor import (
    ResearchWorkspaceActionDescriptor,
)

from .research_workspace_action_scope import (
    ResearchWorkspaceActionScope,
)

from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)


DEFAULT_WORKSPACE_ACTIONS = (

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .CREATE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Create Research Session",

        description=(
            "Start a new research session "
            "in this workspace."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .IMPORT_SNAPSHOT
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Import Workspace Snapshot",

        description=(
            "Transactionally import a "
            "portable research workspace "
            "snapshot."
        ),

        capability=(
            ResearchWorkspaceCapability
            .IMPORT
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .EXPORT_SNAPSHOT
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Export Workspace Snapshot",

        description=(
            "Export a portable snapshot "
            "of the current research "
            "workspace."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SNAPSHOTS
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .REVIEW_INTEGRITY
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Review Workspace Health",

        description=(
            "Inspect detected workspace "
            "integrity issues."
        ),

        capability=(
            ResearchWorkspaceCapability
            .INTEGRITY
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .PREVIEW_REPAIR_PLAN
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Preview Repair Plan",

        description=(
            "Preview a safe repair plan "
            "for detected workspace "
            "integrity issues."
        ),

        capability=(
            ResearchWorkspaceCapability
            .INTEGRITY
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .VIEW_ACTIVITY
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="View Workspace Activity",

        description=(
            "Review recent workspace "
            "activity history."
        ),

        capability=(
            ResearchWorkspaceCapability
            .ACTIVITY
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .VIEW_INSIGHTS
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="View Workspace Insights",

        description=(
            "Review workspace-level "
            "research statistics and "
            "insights."
        ),

        capability=(
            ResearchWorkspaceCapability
            .INSIGHTS
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .REVIEW_READINESS
        ),

        scope=(
            ResearchWorkspaceActionScope
            .WORKSPACE
        ),

        label="Review Workspace Readiness",

        description=(
            "Inspect the workspace's "
            "current operational "
            "readiness."
        ),

        capability=None,

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .CREATE_CHECKPOINT
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Create Checkpoint",

        description=(
            "Checkpoint the selected "
            "research session's current "
            "progress."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .CREATE_BRANCH
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Create Branch",

        description=(
            "Create an independent "
            "research branch from the "
            "selected session."
        ),

        capability=(
            ResearchWorkspaceCapability
            .LINEAGE
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .PAUSE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Pause Session",

        description=(
            "Pause the selected research "
            "session."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .RESUME_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Resume Session",

        description=(
            "Resume the selected paused "
            "research session."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .COMPLETE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Complete Session",

        description=(
            "Mark the selected research "
            "session as completed."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .MANAGE_TAGS
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Manage Tags",

        description=(
            "Assign or remove tags on "
            "the selected research "
            "session."
        ),

        capability=(
            ResearchWorkspaceCapability
            .ORGANIZATION
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .MANAGE_COLLECTIONS
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Manage Collections",

        description=(
            "Add or remove the selected "
            "research session from "
            "collections."
        ),

        capability=(
            ResearchWorkspaceCapability
            .ORGANIZATION
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .VIEW_LINEAGE
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="View Lineage",

        description=(
            "View the selected research "
            "session's ancestry and "
            "descendants."
        ),

        capability=(
            ResearchWorkspaceCapability
            .LINEAGE
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .COMPARE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Compare Session",

        description=(
            "Compare the selected "
            "research session against "
            "another session."
        ),

        capability=(
            ResearchWorkspaceCapability
            .COMPARISON
        ),

        mutating=False,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .ARCHIVE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Archive Session",

        description=(
            "Move the selected research "
            "session out of the active "
            "workspace lifecycle."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),

    ResearchWorkspaceActionDescriptor(

        action=(
            ResearchWorkspaceAction
            .RESTORE_SESSION
        ),

        scope=(
            ResearchWorkspaceActionScope
            .SESSION
        ),

        label="Restore Session",

        description=(
            "Restore the selected "
            "archived research session "
            "to the active workspace."
        ),

        capability=(
            ResearchWorkspaceCapability
            .SESSIONS
        ),

        mutating=True,

        destructive=False,
    ),
)


class ResearchWorkspaceActionCatalog:
    """
    Owns the authoritative set of known
    workspace action descriptors.
    """

    def __init__(

        self,

        actions=None,

    ):

        self._actions = {

            descriptor.action.value:
                descriptor

            for descriptor

            in (

                actions

                or DEFAULT_WORKSPACE_ACTIONS
            )
        }

    def list_actions(self):

        return list(

            self._actions
            .values()
        )

    def get_action(

        self,

        action,

    ):

        if isinstance(

            action,

            ResearchWorkspaceAction,
        ):

            action = (
                action.value
            )

        return (

            self._actions
            .get(
                action
            )
        )

    def list_by_scope(

        self,

        scope,

    ):

        if isinstance(

            scope,

            ResearchWorkspaceActionScope,
        ):

            scope = (
                scope.value
            )

        return [

            descriptor

            for descriptor

            in self.list_actions()

            if (

                descriptor.scope.value

                == scope
            )
        ]

    def list_by_capability(

        self,

        capability,

    ):

        if isinstance(

            capability,

            ResearchWorkspaceCapability,
        ):

            capability = (
                capability.value
            )

        return [

            descriptor

            for descriptor

            in self.list_actions()

            if (

                descriptor.capability

                is not None

                and descriptor.capability.value

                == capability
            )
        ]
