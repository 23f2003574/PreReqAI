from enum import Enum


class LearningIntent(str, Enum):

    EXPLAIN = "explain"

    IMPLEMENT = "implement"

    VISUALIZE = "visualize"

    COMPARE = "compare"

    QUIZ = "quiz"

    SUMMARIZE = "summarize"

    PREREQUISITES = "prerequisites"

    UNKNOWN = "unknown"
