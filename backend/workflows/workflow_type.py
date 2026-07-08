from enum import Enum


class WorkflowType(str, Enum):

    EXPLANATION = "explanation"

    IMPLEMENTATION = "implementation"

    VISUALIZATION = "visualization"

    COMPARISON = "comparison"

    QUIZ = "quiz"

    SUMMARY = "summary"

    PREREQUISITE = "prerequisite"

    DEFAULT = "default"
