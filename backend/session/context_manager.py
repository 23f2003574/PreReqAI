from .context_retriever import (
    RetrievedContext,
)
from .learning_session import (
    LearningSession,
)


class ContextManager:
    """
    Stores the most recently retrieved context inside a learning session.
    """

    def update(
        self,
        session: LearningSession,
        context: RetrievedContext,
    ):
        session.current_context = context
