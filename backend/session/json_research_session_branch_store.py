from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_session_branch import (
    ResearchSessionBranch,
)

from .research_session_branch_store import (
    ResearchSessionBranchStore,
)


class JsonResearchSessionBranchStore(
    ResearchSessionBranchStore
):
    """
    Persists research session branch
    relationships to JSON.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=dict,
        )

    def save(

        self,

        branch:
            ResearchSessionBranch,

    ) -> ResearchSessionBranch:

        branches = self.file.read()

        if branch.id in branches:

            raise ValueError(

                "Research session branch "
                "already exists: "
                f"{branch.id}"
            )

        for data in branches.values():

            existing = (

                ResearchSessionBranch
                .from_dict(

                    data
                )
            )

            if (

                existing.branch_session_id

                == branch.branch_session_id
            ):

                raise ValueError(

                    "Research session already "
                    "has a branch origin: "
                    f"{branch.branch_session_id}"
                )

        branches[
            branch.id
        ] = branch.to_dict()

        self.file.write(
            branches
        )

        return (

            ResearchSessionBranch
            .from_dict(

                branch.to_dict()
            )
        )

    def get(

        self,

        branch_id: str,

    ) -> ResearchSessionBranch | None:

        branches = self.file.read()

        data = branches.get(
            branch_id
        )

        if data is None:

            return None

        return (

            ResearchSessionBranch
            .from_dict(

                data
            )
        )

    def get_by_branch_session(

        self,

        branch_session_id: str,

    ) -> ResearchSessionBranch | None:

        branches = self.file.read()

        for data in branches.values():

            branch = (

                ResearchSessionBranch
                .from_dict(

                    data
                )
            )

            if (

                branch.branch_session_id

                == branch_session_id
            ):

                return branch

        return None

    def list_from_session(

        self,

        source_session_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        branches = self.file.read()

        matching = []

        for data in branches.values():

            branch = (

                ResearchSessionBranch
                .from_dict(

                    data
                )
            )

            if (

                branch.source_session_id

                == source_session_id
            ):

                matching.append(
                    branch
                )

        return sorted(

            matching,

            key=lambda item:
                item.created_at,
        )

    def export_state(self):

        return self.file.read()

    def restore_state(

        self,

        state,

    ) -> None:

        self.file.write(
            state
        )

    def list_from_checkpoint(

        self,

        source_checkpoint_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        branches = self.file.read()

        matching = []

        for data in branches.values():

            branch = (

                ResearchSessionBranch
                .from_dict(

                    data
                )
            )

            if (

                branch.source_checkpoint_id

                == source_checkpoint_id
            ):

                matching.append(
                    branch
                )

        return sorted(

            matching,

            key=lambda item:
                item.created_at,
        )

    def list_all(

        self,

    ) -> list[
        ResearchSessionBranch
    ]:

        branches = self.file.read()

        restored = [

            ResearchSessionBranch
            .from_dict(

                data
            )

            for data

            in branches.values()
        ]

        return sorted(

            restored,

            key=lambda item:
                item.created_at,
        )
