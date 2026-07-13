from abc import (
    ABC,
    abstractmethod,
)

from .research_tag import (
    ResearchTag,
)

from .research_session_tag_assignment import (
    ResearchSessionTagAssignment,
)


class ResearchTagStore(
    ABC,
):
    """
    Persistence boundary for research
    tags and session-tag assignments.
    """

    @abstractmethod
    def save_tag(

        self,

        tag: ResearchTag,

    ) -> None:

        raise NotImplementedError

    @abstractmethod
    def get_tag(

        self,

        tag_id: str,

    ) -> ResearchTag | None:

        raise NotImplementedError

    @abstractmethod
    def get_tag_by_name(

        self,

        name: str,

    ) -> ResearchTag | None:

        raise NotImplementedError

    @abstractmethod
    def list_tags(

        self,

    ) -> list[
        ResearchTag
    ]:

        raise NotImplementedError

    @abstractmethod
    def assign(

        self,

        assignment:
            ResearchSessionTagAssignment,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def unassign(

        self,

        session_id: str,

        tag_id: str,

    ) -> bool:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchTag
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_session_ids_for_tag(

        self,

        tag_id: str,

    ) -> list[
        str
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_assignments_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchSessionTagAssignment
    ]:

        raise NotImplementedError

    @abstractmethod
    def export_state(
        self,
    ):

        raise NotImplementedError

    @abstractmethod
    def restore_state(

        self,

        state,

    ) -> None:

        raise NotImplementedError
