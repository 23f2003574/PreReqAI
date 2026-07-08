from enum import Enum


class LearningIntent(str, Enum):
    """
    Defined here (not in backend.workflows) because backend.workflows'
    own modules (e.g. ExplanationWorkflow) import from backend.session —
    sourcing it here avoids a circular import back into backend.workflows.
    """

    EXPLAIN = "explain"

    IMPLEMENT = "implement"

    VISUALIZE = "visualize"

    COMPARE = "compare"

    QUIZ = "quiz"

    SUMMARIZE = "summarize"

    PREREQUISITES = "prerequisites"

    UNKNOWN = "unknown"
