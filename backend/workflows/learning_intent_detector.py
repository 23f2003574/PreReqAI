from backend.session import (
    LearningIntent,
)


class LearningIntentDetector:
    """
    Detects the educational intent behind
    a learner's question.
    """

    KEYWORDS = {

        LearningIntent.IMPLEMENT: [

            "implement",

            "code",

            "pytorch",

            "tensorflow",
        ],

        LearningIntent.VISUALIZE: [

            "visualize",

            "diagram",

            "draw",

            "image",
        ],

        LearningIntent.COMPARE: [

            "compare",

            "difference",

            "versus",

            "vs",
        ],

        LearningIntent.QUIZ: [

            "quiz",

            "test me",

            "question",
        ],

        LearningIntent.SUMMARIZE: [

            "summarize",

            "summary",

            "brief",
        ],

        LearningIntent.PREREQUISITES: [

            "prerequisite",

            "before",

            "prepare",
        ],

        LearningIntent.EXAMPLE: [

            "example",

            "sample",

            "walk through",

            "demonstrate",

            "illustrate",
        ],

        LearningIntent.HINT: [

            "hint",

            "clue",

            "help me",

            "stuck",

            "nudge",
        ],

        LearningIntent.EXPLAIN: [

            "explain",

            "what is",

            "why",

            "understand",
        ],
    }

    def detect(

        self,

        question: str,

    ) -> LearningIntent:

        query = question.lower()

        for intent, keywords in self.KEYWORDS.items():

            if any(

                keyword in query

                for keyword in keywords

            ):

                return intent

        return LearningIntent.UNKNOWN
