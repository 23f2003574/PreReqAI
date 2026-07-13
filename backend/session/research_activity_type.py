from enum import (
    Enum,
)


class ResearchActivityType(
    str,
    Enum,
):
    """
    Enumerates meaningful research
    workspace activity events.
    """

    SESSION_CREATED = (
        "session.created"
    )

    SESSION_ACTIVATED = (
        "session.activated"
    )

    SESSION_RENAMED = (
        "session.renamed"
    )

    SESSION_DESCRIPTION_UPDATED = (
        "session.description_updated"
    )

    SESSION_STATUS_CHANGED = (
        "session.status_changed"
    )

    SESSION_ARCHIVED = (
        "session.archived"
    )

    SESSION_RESTORED = (
        "session.restored"
    )

    CHECKPOINT_CREATED = (
        "checkpoint.created"
    )

    VERSION_CREATED = (
        "version.created"
    )

    BRANCH_CREATED = (
        "branch.created"
    )

    TAG_ASSIGNED = (
        "tag.assigned"
    )

    TAG_REMOVED = (
        "tag.removed"
    )

    COLLECTION_CREATED = (
        "collection.created"
    )

    COLLECTION_UPDATED = (
        "collection.updated"
    )

    COLLECTION_DELETED = (
        "collection.deleted"
    )

    COLLECTION_SESSION_ADDED = (
        "collection.session_added"
    )

    COLLECTION_SESSION_REMOVED = (
        "collection.session_removed"
    )

    SESSION_COMPARED = (
        "session.compared"
    )
