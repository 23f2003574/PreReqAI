from .object_action import (
    ObjectAction,
)
from .research_object_type import (
    ResearchObjectType,
)

CAPABILITY_MAP: dict[
    ResearchObjectType, list[ObjectAction]
] = {
    ResearchObjectType.CONCEPT: [
        ObjectAction.EXPLAIN,
        ObjectAction.VISUALIZE,
        ObjectAction.IMPLEMENT,
        ObjectAction.COMPARE,
        ObjectAction.QUIZ,
        ObjectAction.SHOW_PREREQUISITES,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.EQUATION: [
        ObjectAction.EXPLAIN,
        ObjectAction.VISUALIZE,
        ObjectAction.IMPLEMENT,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.FIGURE: [
        ObjectAction.EXPLAIN,
        ObjectAction.VISUALIZE,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.EXPERIMENT: [
        ObjectAction.EXPLAIN,
        ObjectAction.COMPARE,
        ObjectAction.IMPLEMENT,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.SECTION: [
        ObjectAction.EXPLAIN,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.REFERENCE: [
        ObjectAction.EXPLAIN,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.CITATION: [
        ObjectAction.EXPLAIN,
        ObjectAction.SHOW_RELATIONS,
    ],
    ResearchObjectType.RELATED_PAPER: [
        ObjectAction.EXPLAIN,
        ObjectAction.COMPARE,
        ObjectAction.SHOW_RELATIONS,
    ],
}

DEFAULT_CAPABILITIES: list[ObjectAction] = [
    ObjectAction.EXPLAIN,
]


def get_capabilities(
    object_type: ResearchObjectType,
) -> list[ObjectAction]:
    """
    Returns the actions a given research
    object type supports, so callers can
    ask an object what it can do instead
    of hardcoding behavior per type.
    """

    return CAPABILITY_MAP.get(
        object_type, DEFAULT_CAPABILITIES
    )
