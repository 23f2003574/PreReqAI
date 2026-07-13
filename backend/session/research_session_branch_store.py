from abc import (
    ABC,
    abstractmethod,
)

from .research_session_branch import (
    ResearchSessionBranch,
)


class ResearchSessionBranchStore(
    ABC
):
    """
    Defines persistence operations
    for research session lineage
    relationships.
    """

    @abstractmethod
    def save(

        self,

        branch:
            ResearchSessionBranch,

    ) -> ResearchSessionBranch:

        raise NotImplementedError

    @abstractmethod
    def get(

        self,

        branch_id: str,

    ) -> ResearchSessionBranch | None:

        raise NotImplementedError

    @abstractmethod
    def get_by_branch_session(

        self,

        branch_session_id: str,

    ) -> ResearchSessionBranch | None:

        raise NotImplementedError

    @abstractmethod
    def list_from_session(

        self,

        source_session_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_from_checkpoint(

        self,

        source_checkpoint_id: str,

    ) -> list[
        ResearchSessionBranch
    ]:

        raise NotImplementedError
