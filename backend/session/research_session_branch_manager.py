from copy import deepcopy

from uuid import uuid4

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)

from .research_session_branch import (
    ResearchSessionBranch,
)


class ResearchSessionBranchManager:
    """
    Coordinates creation and querying
    of independent research sessions
    branched from historical checkpoints.
    """

    def __init__(

        self,

        checkpoint_store,

        checkpoint_manager,

        version_manager,

        session_manager,

        session_restorer,

        branch_store,

        workspace_factory,

    ):

        self.checkpoint_store = (
            checkpoint_store
        )

        self.checkpoint_manager = (
            checkpoint_manager
        )

        self.version_manager = (
            version_manager
        )

        self.session_manager = (
            session_manager
        )

        self.session_restorer = (
            session_restorer
        )

        self.branch_store = (
            branch_store
        )

        self.workspace_factory = (
            workspace_factory
        )

    def create_from_checkpoint(

        self,

        checkpoint_id: str,

        branch_session_id:
            str | None = None,

        metadata:
            dict | None = None,

    ):

        checkpoint = (

            self.checkpoint_store
            .get(

                checkpoint_id
            )
        )

        if checkpoint is None:

            raise ValueError(

                "Research checkpoint "
                "does not exist: "
                f"{checkpoint_id}"
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

        new_session_id = (

            branch_session_id

            or str(
                uuid4()
            )
        )

        existing = (

            self.session_manager
            .load_session(

                new_session_id
            )
        )

        if existing is not None:

            raise ValueError(

                "Research session already "
                "exists: "
                f"{new_session_id}"
            )

        branch_workspace = (

            self.workspace_factory()
        )

        restored_workspace = (

            self.session_restorer
            .restore_snapshot(

                deepcopy(
                    version.snapshot
                ),

                branch_workspace,
            )
        )

        branch_snapshot = (

            self.session_manager
            .save_workspace(

                session_id=(
                    new_session_id
                ),

                workspace=(
                    restored_workspace
                ),

                paper_id=(

                    version.snapshot
                    .paper_id
                ),

                paper_title=(

                    version.snapshot
                    .paper_title
                ),
            )
        )

        branch = ResearchSessionBranch(

            source_session_id=(

                checkpoint
                .session_id
            ),

            source_checkpoint_id=(
                checkpoint.id
            ),

            source_version_id=(
                version.id
            ),

            branch_session_id=(
                new_session_id
            ),

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        stored_branch = (

            self.branch_store
            .save(

                branch
            )
        )

        initial_checkpoint = (

            self.checkpoint_manager
            .checkpoint(

                session_id=(
                    new_session_id
                ),

                workspace=(
                    restored_workspace
                ),

                reason=(

                    ResearchCheckpointReason
                    .SESSION_BRANCHED
                ),

                paper_id=(

                    version.snapshot
                    .paper_id
                ),

                paper_title=(

                    version.snapshot
                    .paper_title
                ),

                metadata={

                    "source_session_id":
                        checkpoint.session_id,

                    "source_checkpoint_id":
                        checkpoint.id,

                    "source_version_id":
                        version.id,

                    "branch_id":
                        stored_branch.id,
                },
            )
        )

        return (

            stored_branch,

            initial_checkpoint,

            restored_workspace,
        )
