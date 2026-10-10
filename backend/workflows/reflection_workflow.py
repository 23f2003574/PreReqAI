from backend.session import (
    ContextRetriever,
    ContextManager,
)

from backend.tutor import (
    RuleBasedTutor,
    TutorMode,
)


class ReflectionWorkflow:
    """
    Encourages learners to consolidate
    their understanding through guided
    reflection.
    """

    def __init__(self):

        self.context_retriever = (
            ContextRetriever()
        )

        self.context_manager = (
            ContextManager()
        )

        self.tutor = RuleBasedTutor()

    def execute(

        self,

        session,

        paper,

        question,

    ):

        context = (

            self.context_retriever.retrieve(

                paper,

                question,
            )
        )

        self.context_manager.update(

            session,

            context,
        )

        response = self.tutor.answer(

            session,

            paper,

            context,

            question,

            TutorMode.REFLECTION,
        )

        return response
