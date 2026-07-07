from .base_tutor import (
    BaseTutor,
)

from .tutor_response import (
    TutorResponse,
)


class RuleBasedTutor(BaseTutor):
    """
    Temporary tutor used before the
    LLM tutor is introduced.
    """

    def answer(

        self,

        paper,

        context,

        question,

    ):

        return TutorResponse(

            answer=(
                "A tutoring model has not yet "
                "been configured."
            ),

            confidence=0.0,

            supporting_concepts=context.concepts,

            supporting_sections=context.sections,

            suggested_followups=[

                "Explain this concept",

                "Show prerequisite path",

                "Summarize this section",
            ],
        )
