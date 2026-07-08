from enum import Enum


class WorkflowType(str, Enum):
    """
    Defined here (not in backend.workflows) because backend.workflows'
    own modules (e.g. ExplanationWorkflow) import from backend.session —
    sourcing it here avoids a circular import back into backend.workflows.
    """

    EXPLANATION = "explanation"

    IMPLEMENTATION = "implementation"

    VISUALIZATION = "visualization"

    COMPARISON = "comparison"

    QUIZ = "quiz"

    SUMMARY = "summary"

    PREREQUISITE = "prerequisite"

    EXAMPLE = "example"

    DEFAULT = "default"
