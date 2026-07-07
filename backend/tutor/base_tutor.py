from abc import (
    ABC,
    abstractmethod,
)

from backend.models import (
    Paper,
)

from backend.session import (
    LearningSession,
    RetrievedContext,
)

from .tutor_response import (
    TutorResponse,
)


class BaseTutor(ABC):
    """
    Base interface implemented by every
    tutoring engine.
    """

    @abstractmethod
    def answer(

        self,

        session: LearningSession,

        paper: Paper,

        context: RetrievedContext,

        question: str,

    ) -> TutorResponse:

        pass
