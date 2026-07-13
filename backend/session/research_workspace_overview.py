from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceOverview:
    """
    High-level counts describing the
    current research workspace.
    """

    total_sessions: int

    archived_sessions: int

    unarchived_sessions: int

    root_sessions: int

    branch_sessions: int

    total_tags: int

    total_collections: int

    total_activity_events: int

    def to_dict(self):

        return {

            "total_sessions":
                self.total_sessions,

            "archived_sessions":
                self.archived_sessions,

            "unarchived_sessions":
                self.unarchived_sessions,

            "root_sessions":
                self.root_sessions,

            "branch_sessions":
                self.branch_sessions,

            "total_tags":
                self.total_tags,

            "total_collections":
                self.total_collections,

            "total_activity_events":
                self.total_activity_events,
        }
