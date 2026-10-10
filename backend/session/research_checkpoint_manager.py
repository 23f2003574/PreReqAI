from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_checkpoint_policy import (
    ResearchCheckpointPolicy,
)

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)


class ResearchCheckpointManager:
    """
    Coordinates automatic persistence
    checkpoints for active research
    sessions.
    """

    def __init__(

        self,

        session_manager,

        checkpoint_store,

        version_manager,

        policy=None,

    ):

        self.session_manager = (
            session_manager
        )

        self.checkpoint_store = (
            checkpoint_store
        )

        self.version_manager = (
            version_manager
        )

        self.policy = (

            policy

            or ResearchCheckpointPolicy()
        )

    def checkpoint(

        self,

        session_id: str,

        workspace,

        reason:
            ResearchCheckpointReason,

        paper_id: str | None = None,

        paper_title: str | None = None,

        metadata: dict | None = None,

    ) -> ResearchCheckpoint | None:

        if not self.policy.should_checkpoint(

            reason
        ):

            return None

        snapshot = (

            self.session_manager
            .save_workspace(

                session_id=session_id,

                workspace=workspace,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

        version = (

            self.version_manager
            .create(

                snapshot=snapshot,

                metadata={

                    "checkpoint_reason":
                        reason.value,

                    **(

                        metadata

                        if metadata is not None

                        else {}
                    ),
                },
            )
        )

        checkpoint = ResearchCheckpoint(

            session_id=session_id,

            reason=reason,

            snapshot_updated_at=(
                snapshot.updated_at
            ),

            snapshot_version_id=(
                version.id
            ),

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        return (

            self.checkpoint_store
            .save(

                checkpoint
            )
        )

    def list_checkpoints(

        self,

        session_id: str,

    ):

        return (

            self.checkpoint_store
            .list_for_session(

                session_id
            )
        )

    def latest_checkpoint(

        self,

        session_id: str,

    ):

        return (

            self.checkpoint_store
            .latest_for_session(

                session_id
            )
        )

    def get_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_store
            .get(

                checkpoint_id
            )
        )

    def delete_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_store
            .delete(

                checkpoint_id
            )
        )
