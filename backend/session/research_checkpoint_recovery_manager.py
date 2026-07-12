from datetime import datetime

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)

from .research_recovery_result import (
    ResearchRecoveryResult,
)


class ResearchCheckpointRecoveryManager:
    """
    Coordinates safe non-destructive
    recovery of historical research
    checkpoint states.
    """

    def __init__(

        self,

        checkpoint_manager,

        version_manager,

        session_restorer,

    ):

        self.checkpoint_manager = (
            checkpoint_manager
        )

        self.version_manager = (
            version_manager
        )

        self.session_restorer = (
            session_restorer
        )

    def recover(

        self,

        checkpoint_id: str,

        current_workspace,

        session_id: str,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        source_checkpoint = (

            self.checkpoint_manager
            .get_checkpoint(

                checkpoint_id
            )
        )

        if source_checkpoint is None:

            raise ValueError(

                "Research checkpoint "
                "does not exist: "
                f"{checkpoint_id}"
            )

        if (

            source_checkpoint.session_id

            != session_id
        ):

            raise ValueError(

                "Research checkpoint "
                "does not belong to "
                f"session: {session_id}"
            )

        version_id = (

            source_checkpoint
            .snapshot_version_id
        )

        if version_id is None:

            raise ValueError(

                "Research checkpoint "
                "does not reference an "
                "immutable session version"
            )

        source_version = (

            self.version_manager
            .get(

                version_id
            )
        )

        if source_version is None:

            raise ValueError(

                "Research session version "
                "does not exist: "
                f"{version_id}"
            )

        safety_checkpoint = (

            self.checkpoint_manager
            .checkpoint(

                session_id=session_id,

                workspace=current_workspace,

                reason=(

                    ResearchCheckpointReason
                    .RECOVERY_SAFETY
                ),

                paper_id=paper_id,

                paper_title=paper_title,

                metadata={

                    "target_checkpoint_id":
                        checkpoint_id,

                    "target_version_id":
                        version_id,
                },
            )
        )

        if safety_checkpoint is None:

            raise RuntimeError(

                "Could not create recovery "
                "safety checkpoint"
            )

        restored_workspace = (

            self.session_restorer
            .restore_snapshot(

                source_version.snapshot,

                current_workspace,
            )
        )

        recovery_checkpoint = (

            self.checkpoint_manager
            .checkpoint(

                session_id=session_id,

                workspace=restored_workspace,

                reason=(

                    ResearchCheckpointReason
                    .CHECKPOINT_RESTORED
                ),

                paper_id=(

                    source_version
                    .snapshot
                    .paper_id
                ),

                paper_title=(

                    source_version
                    .snapshot
                    .paper_title
                ),

                metadata={

                    "source_checkpoint_id":
                        checkpoint_id,

                    "source_version_id":
                        version_id,

                    "safety_checkpoint_id":
                        safety_checkpoint.id,
                },
            )
        )

        if recovery_checkpoint is None:

            raise RuntimeError(

                "Could not create recovery "
                "checkpoint"
            )

        return (

            restored_workspace,

            ResearchRecoveryResult(

                session_id=session_id,

                source_checkpoint_id=(
                    checkpoint_id
                ),

                source_version_id=(
                    version_id
                ),

                safety_checkpoint_id=(
                    safety_checkpoint.id
                ),

                recovery_checkpoint_id=(
                    recovery_checkpoint.id
                ),

                recovered_at=(
                    datetime.utcnow()
                ),
            )
        )
