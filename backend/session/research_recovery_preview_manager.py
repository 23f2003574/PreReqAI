from .research_recovery_preview import (
    ResearchRecoveryPreview,
)


class ResearchRecoveryPreviewManager:
    """
    Builds read-only previews of
    historical checkpoint recovery.
    """

    def __init__(

        self,

        checkpoint_manager,

        version_manager,

        session_manager,

        comparator,

    ):

        self.checkpoint_manager = (
            checkpoint_manager
        )

        self.version_manager = (
            version_manager
        )

        self.session_manager = (
            session_manager
        )

        self.comparator = (
            comparator
        )

    def preview(

        self,

        checkpoint_id: str,

        session_id: str,

        current_workspace,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        checkpoint = (

            self.checkpoint_manager
            .get_checkpoint(

                checkpoint_id
            )
        )

        if checkpoint is None:

            raise ValueError(

                "Research checkpoint "
                "does not exist: "
                f"{checkpoint_id}"
            )

        if (

            checkpoint.session_id

            != session_id
        ):

            raise ValueError(

                "Research checkpoint "
                "does not belong to "
                f"session: {session_id}"
            )

        version_id = (

            checkpoint
            .snapshot_version_id
        )

        if version_id is None:

            raise ValueError(

                "Research checkpoint "
                "does not reference an "
                "immutable session version"
            )

        version = (

            self.version_manager
            .get(

                version_id
            )
        )

        if version is None:

            raise ValueError(

                "Research session version "
                "does not exist: "
                f"{version_id}"
            )

        current_snapshot = (

            self.session_manager
            .snapshot_workspace(

                session_id=session_id,

                workspace=(
                    current_workspace
                ),

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

        comparison = (

            self.comparator
            .compare(

                current_snapshot=(
                    current_snapshot
                ),

                target_snapshot=(
                    version.snapshot
                ),
            )
        )

        return ResearchRecoveryPreview(

            session_id=session_id,

            checkpoint_id=(
                checkpoint_id
            ),

            snapshot_version_id=(
                version_id
            ),

            comparison=comparison,
        )
