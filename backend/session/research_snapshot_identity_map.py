from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchSnapshotIdentityMap:
    """
    Maps imported snapshot identities to
    their final local workspace identities.
    """

    sessions: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    checkpoints: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    versions: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    branches: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    tags: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    collections: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    activity_events: dict[
        str,
        str,
    ] = field(
        default_factory=dict,
    )

    def map_session(

        self,

        session_id,

    ):

        return self.sessions.get(

            session_id,

            session_id,
        )

    def map_checkpoint(

        self,

        checkpoint_id,

    ):

        return self.checkpoints.get(

            checkpoint_id,

            checkpoint_id,
        )

    def map_version(

        self,

        version_id,

    ):

        return self.versions.get(

            version_id,

            version_id,
        )

    def map_branch(

        self,

        branch_id,

    ):

        return self.branches.get(

            branch_id,

            branch_id,
        )

    def map_tag(

        self,

        tag_id,

    ):

        return self.tags.get(

            tag_id,

            tag_id,
        )

    def map_collection(

        self,

        collection_id,

    ):

        return self.collections.get(

            collection_id,

            collection_id,
        )

    def map_activity_event(

        self,

        event_id,

    ):

        return self.activity_events.get(

            event_id,

            event_id,
        )

    def to_dict(self):

        return {

            "sessions":
                dict(
                    self.sessions
                ),

            "checkpoints":
                dict(
                    self.checkpoints
                ),

            "versions":
                dict(
                    self.versions
                ),

            "branches":
                dict(
                    self.branches
                ),

            "tags":
                dict(
                    self.tags
                ),

            "collections":
                dict(
                    self.collections
                ),

            "activity_events":
                dict(
                    self.activity_events
                ),
        }
