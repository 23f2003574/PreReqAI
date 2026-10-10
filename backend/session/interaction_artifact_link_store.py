from abc import (
    ABC,
    abstractmethod,
)

from .interaction_artifact_link import (
    InteractionArtifactLink,
)


class InteractionArtifactLinkStore(ABC):
    """
    Defines persistence operations
    for interaction-to-artifact links.
    """

    @abstractmethod
    def save(

        self,

        link:
            InteractionArtifactLink,

    ) -> InteractionArtifactLink:

        raise NotImplementedError

    @abstractmethod
    def list_for_interaction(

        self,

        interaction_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_for_artifact(

        self,

        artifact_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        raise NotImplementedError

    @abstractmethod
    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        raise NotImplementedError
