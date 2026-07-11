from enum import Enum


class LearningContentType(str, Enum):
    """
    Represents the educational content
    displayed inside the learning panel.
    """

    EXPLANATION = "explanation"

    VISUALIZATION = "visualization"

    IMPLEMENTATION = "implementation"

    COMPARISON = "comparison"

    QUIZ = "quiz"

    PREREQUISITE = "prerequisite"

    FOLLOW_UP = "follow_up"

    GENERAL = "general"
