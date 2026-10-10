from enum import Enum


class ResearchStateChangeType(
    str,
    Enum,
):
    """
    Describes how a research session
    value differs between two states.
    """

    ADDED = "added"

    REMOVED = "removed"

    CHANGED = "changed"
