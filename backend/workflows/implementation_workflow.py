from backend.session import (
    ContextRetriever,
    ContextManager,
)

from backend.tutor import (
    RuleBasedTutor,
    TutorMode,
)


class ImplementationWorkflow:
    """
    Executes the implementation learning
    workflow for practical questions.
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

            TutorMode.IMPLEMENTATION,
        )

        return response
