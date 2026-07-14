from dataclasses import (
    dataclass,
    field,
)

from .research_activity_event import (
    ResearchActivityEvent,
)

from .research_session_list_item import (
    ResearchSessionListItem,
)

from .research_workspace_capability_descriptor import (
    ResearchWorkspaceCapabilityDescriptor,
)

from .research_workspace_overview import (
    ResearchWorkspaceOverview,
)

from .research_workspace_readiness_assessment import (
    ResearchWorkspaceReadinessAssessment,
)


@dataclass
class ResearchWorkspaceBootstrapProjection:
    """
    Assembles the initial consumer-facing
    research workspace context from existing
    capability, readiness, overview, session,
    and activity read models.
    """

    capabilities: list[
        ResearchWorkspaceCapabilityDescriptor
    ]

    readiness: (
        ResearchWorkspaceReadinessAssessment
    )

    overview: (
        ResearchWorkspaceOverview
    )

    recent_sessions: list[
        ResearchSessionListItem
    ] = field(
        default_factory=list,
    )

    recent_activity: list[
        ResearchActivityEvent
    ] = field(
        default_factory=list,
    )

    warnings: list[
        str
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "capabilities": [

                capability.to_dict()

                for capability

                in self.capabilities
            ],

            "readiness":
                self.readiness.to_dict(),

            "overview":
                self.overview.to_dict(),

            "recent_sessions": [

                session.to_dict()

                for session

                in self.recent_sessions
            ],

            "recent_activity": [

                event.to_dict()

                for event

                in self.recent_activity
            ],

            "warnings":
                list(
                    self.warnings
                ),
        }
