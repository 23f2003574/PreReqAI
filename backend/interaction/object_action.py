from enum import Enum


class ObjectAction(str, Enum):

    EXPLAIN = "explain"

    VISUALIZE = "visualize"

    IMPLEMENT = "implement"

    COMPARE = "compare"

    QUIZ = "quiz"

    SHOW_PREREQUISITES = (
        "show_prerequisites"
    )

    SHOW_RELATIONS = (
        "show_relations"
    )
