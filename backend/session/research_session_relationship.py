from enum import Enum


class ResearchSessionRelationship(
    str,
    Enum,
):
    """
    Describes the lineage relationship
    between two research sessions.
    """

    SAME = "same"

    ANCESTOR = "ancestor"

    DESCENDANT = "descendant"

    SIBLING = "sibling"

    COUSIN = "cousin"

    UNRELATED = "unrelated"
