from enum import Enum


class ResearchArtifactType(
    str,
    Enum,
):
    """
    Defines durable artifact categories
    produced during research and learning.
    """

    EXPLANATION = "explanation"

    VISUALIZATION = "visualization"

    IMPLEMENTATION = "implementation"

    COMPARISON = "comparison"

    QUIZ = "quiz"

    SUMMARY = "summary"

    DERIVATION = "derivation"

    EXPLORATION = "exploration"

    OTHER = "other"
