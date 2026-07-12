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

        policy=None,

    ):

        self.session_manager = (
            session_manager
        )

        self.policy = (

            policy

            or ResearchCheckpointPolicy()
        )

        self._checkpoints: dict[
            str,
            list[ResearchCheckpoint],
        ] = {}

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

        checkpoint = ResearchCheckpoint(

            session_id=session_id,

            reason=reason,

            snapshot_updated_at=(
                snapshot.updated_at
            ),

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        self._checkpoints.setdefault(

            session_id,

            [],
        ).append(
            checkpoint
        )

        return checkpoint

    def list_checkpoints(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpoint
    ]:

        return list(

            self._checkpoints.get(

                session_id,

                [],
            )
        )

    def latest_checkpoint(

        self,

        session_id: str,

    ) -> ResearchCheckpoint | None:

        checkpoints = (

            self.list_checkpoints(

                session_id
            )
        )

        if not checkpoints:

            return None

        return checkpoints[-1]
