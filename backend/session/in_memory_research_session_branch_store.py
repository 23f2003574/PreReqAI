from copy import deepcopy

from .research_session_branch import (
    ResearchSessionBranch,
)

from .research_session_branch_store import (
    ResearchSessionBranchStore,
)


class InMemoryResearchSessionBranchStore(
    ResearchSessionBranchStore
):
    """
    Stores research session branch
    relationships in memory.
    """

    def __init__(self):

        self._branches: dict[

            str,

            ResearchSessionBranch,

        ] = {}

    def save(

        self,

        branch:
            ResearchSessionBranch,

    ) -> ResearchSessionBranch:

        if branch.id in self._branches:

            raise ValueError(

                "Research session branch "
                "already exists: "
                f"{branch.id}"
            )

        if (

            self.get_by_branch_session(

                branch.branch_session_id
            )

            is not None
        ):

            raise ValueError(

                "Research session already "
                "has a branch origin: "
                f"{branch.branch_session_id}"
            )

        stored = deepcopy(
            branch
        )

        self._branches[
            branch.id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        branch_id: str,

    ) -> ResearchSessionBranch | None:

        branch = (

            self._branches.get(
                branch_id
            )
        )

        if branch is None:

            return None

        return deepcopy(
            branch
        )

    def get_by_branch_session(

        self,

        branch_session_id: str,

    ) -> ResearchSessionBranch | None:

        for branch in (

            self._branches.values()
        ):

            if (

                branch.branch_session_id

                == branch_session_id
            ):

                return deepcopy(
                    branch
                )

        return None

    def list_from_session(

        self,

        source_session_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        branches = [

            branch

            for branch

            in self._branches.values()

            if (

                branch.source_session_id

                == source_session_id
            )
        ]

        return [

            deepcopy(
                branch
            )

            for branch

            in sorted(

                branches,

                key=lambda item:
                    item.created_at,
            )
        ]

    def list_from_checkpoint(

        self,

        source_checkpoint_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        branches = [

            branch

            for branch

            in self._branches.values()

            if (

                branch.source_checkpoint_id

                == source_checkpoint_id
            )
        ]

        return [

            deepcopy(
                branch
            )

            for branch

            in sorted(

                branches,

                key=lambda item:
                    item.created_at,
            )
        ]
