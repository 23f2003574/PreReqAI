from enum import Enum


class TutorMode(str, Enum):
    """
    Defined here (not in backend.tutor) because backend.tutor's own
    modules import from backend.session — sourcing it here avoids a
    circular import back into backend.tutor.
    """

    INTUITION = "intuition"

    MATHEMATICS = "mathematics"

    IMPLEMENTATION = "implementation"

    PREREQUISITES = "prerequisites"

    SUMMARY = "summary"

    ANALOGY = "analogy"

    MISCONCEPTION = "misconception"
