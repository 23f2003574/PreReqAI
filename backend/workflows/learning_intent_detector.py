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

        LearningIntent.FOLLOW_UP: [

            "what next",

            "next step",

            "study next",

            "what should i learn next",

            "continue",

            "where do i go from here",
        ],

        LearningIntent.REFLECTION: [

            "reflect",

            "reflection",

            "what did i learn",

            "review my understanding",

            "recap my learning",
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
