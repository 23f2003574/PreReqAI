from enum import Enum


class ResearchHistorySortOrder(
    str,
    Enum,
):
    """
    Defines chronological ordering
    for research history results.
    """

    NEWEST = "newest"

    OLDEST = "oldest"
