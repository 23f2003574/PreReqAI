from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)

from .research_workspace_capability_descriptor import (
    ResearchWorkspaceCapabilityDescriptor,
)


class ResearchWorkspaceCapabilities:
    """
    Provides discoverable metadata describing
    the public research workspace surface.
    """

    def __init__(self):

        self._capabilities = (
            self._build_capabilities()
        )

    def _build_capabilities(self):

        return {

            ResearchWorkspaceCapability
            .SESSIONS.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .SESSIONS.value
                    ),

                    description=(

                        "Create, inspect, profile, "
                        "checkpoint, and manage "
                        "research sessions."
                    ),

                    operations=[

                        "create_session",

                        "get_session",

                        "get_session_profile",

                        "update_session_profile",

                        "update_lifecycle_state",

                        "create_checkpoint",
                    ],
                ),

            ResearchWorkspaceCapability
            .DISCOVERY.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .DISCOVERY.value
                    ),

                    description=(

                        "Search, filter, sort, "
                        "and paginate research sessions."
                    ),

                    operations=[

                        "search_sessions",
                    ],
                ),

            ResearchWorkspaceCapability
            .LINEAGE.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .LINEAGE.value
                    ),

                    description=(

                        "Create independent research "
                        "branches and inspect lineage."
                    ),

                    operations=[

                        "branch_session",

                        "get_lineage",

                        "get_ancestors",

                        "get_descendants",
                    ],
                ),

            ResearchWorkspaceCapability
            .COMPARISON.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .COMPARISON.value
                    ),

                    description=(

                        "Compare research sessions "
                        "and analyze lineage-aware "
                        "divergence."
                    ),

                    operations=[

                        "compare_sessions",
                    ],
                ),

            ResearchWorkspaceCapability
            .ORGANIZATION.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .ORGANIZATION.value
                    ),

                    description=(

                        "Organize research using "
                        "tags and collections."
                    ),

                    operations=[

                        "create_tag",

                        "assign_tag",

                        "remove_tag_assignment",

                        "create_collection",

                        "add_collection_member",

                        "remove_collection_member",
                    ],
                ),

            ResearchWorkspaceCapability
            .ACTIVITY.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .ACTIVITY.value
                    ),

                    description=(

                        "Inspect human-readable "
                        "research activity history."
                    ),

                    operations=[

                        "get_activity",
                    ],
                ),

            ResearchWorkspaceCapability
            .INSIGHTS.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .INSIGHTS.value
                    ),

                    description=(

                        "Compute workspace-level "
                        "research statistics and insights."
                    ),

                    operations=[

                        "get_workspace_insights",
                    ],
                ),

            ResearchWorkspaceCapability
            .SNAPSHOTS.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .SNAPSHOTS.value
                    ),

                    description=(

                        "Export portable research "
                        "workspace snapshots."
                    ),

                    operations=[

                        "export_workspace",

                        "serialize_snapshot",
                    ],
                ),

            ResearchWorkspaceCapability
            .IMPORT.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .IMPORT.value
                    ),

                    description=(

                        "Preview and transactionally "
                        "import portable snapshots."
                    ),

                    operations=[

                        "preview_import",

                        "import_snapshot",
                    ],
                ),

            ResearchWorkspaceCapability
            .INTEGRITY.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .INTEGRITY.value
                    ),

                    description=(

                        "Audit workspace integrity "
                        "and plan repairs."
                    ),

                    operations=[

                        "audit_workspace",

                        "plan_repairs",
                    ],
                ),

            ResearchWorkspaceCapability
            .CHANGE_FEED.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .CHANGE_FEED.value
                    ),

                    description=(

                        "Read ordered workspace "
                        "changes using sequence cursors."
                    ),

                    operations=[

                        "get_changes",

                        "get_latest_change_sequence",
                    ],
                ),

            ResearchWorkspaceCapability
            .SUBSCRIPTIONS.value:

                ResearchWorkspaceCapabilityDescriptor(

                    name=(
                        ResearchWorkspaceCapability
                        .SUBSCRIPTIONS.value
                    ),

                    description=(

                        "Subscribe to live in-process "
                        "workspace change notifications."
                    ),

                    operations=[

                        "subscribe",

                        "unsubscribe",
                    ],
                ),
        }

    def list_capabilities(self):

        return list(

            self._capabilities
            .values()
        )

    def get_capability(

        self,

        name,

    ):

        if isinstance(

            name,

            ResearchWorkspaceCapability,
        ):

            name = (
                name.value
            )

        return (

            self._capabilities
            .get(
                name
            )
        )

    def supports(

        self,

        capability,

    ):

        descriptor = (

            self.get_capability(

                capability
            )
        )

        return (

            descriptor is not None

            and descriptor.enabled
        )

    def to_dict(self):

        return {

            "capabilities": [

                descriptor.to_dict()

                for descriptor

                in self.list_capabilities()
            ]
        }
