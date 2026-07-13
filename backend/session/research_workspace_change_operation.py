from enum import (
    Enum,
)


class ResearchWorkspaceChangeOperation(
    str,
    Enum,
):
    """
    Describes the kind of workspace
    state transition represented by
    a change event.
    """

    CREATED = (
        "created"
    )

    UPDATED = (
        "updated"
    )

    DELETED = (
        "deleted"
    )

    RESTORED = (
        "restored"
    )

    IMPORTED = (
        "imported"
    )

    REPAIRED = (
        "repaired"
    )
