from enum import Enum


class ResearchSessionSortOrder(
    str,
    Enum,
):
    """
    Defines ordering for research
    session discovery results.
    """

    CREATED_NEWEST = (
        "created_newest"
    )

    CREATED_OLDEST = (
        "created_oldest"
    )

    UPDATED_NEWEST = (
        "updated_newest"
    )

    UPDATED_OLDEST = (
        "updated_oldest"
    )

    NAME_ASCENDING = (
        "name_ascending"
    )

    NAME_DESCENDING = (
        "name_descending"
    )
