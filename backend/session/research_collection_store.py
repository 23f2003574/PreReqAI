from abc import (
    ABC,
    abstractmethod,
)

from .research_collection import (
    ResearchCollection,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)


class ResearchCollectionStore(
    ABC,
):
    """
    Persistence boundary for research
    collections and memberships.
    """

    @abstractmethod
    def save_collection(

        self,

        collection:
            ResearchCollection,

    ) -> None:

        raise NotImplementedError

    @abstractmethod
    def get_collection(

        self,

        collection_id: str,

    ) -> ResearchCollection | None:

        raise NotImplementedError

    @abstractmethod
    def list_collections(

        self,

    ) -> list[
        ResearchCollection
    ]:

        raise NotImplementedError

    @abstractmethod
    def delete_collection(

        self,

        collection_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def add_membership(

        self,

        membership:
            ResearchCollectionMembership,

    ) -> None:

        raise NotImplementedError

    @abstractmethod
    def remove_membership(

        self,

        collection_id: str,

        session_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def list_session_ids(

        self,

        collection_id: str,

    ) -> list[
        str
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCollection
    ]:

        raise NotImplementedError
