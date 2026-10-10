from enum import Enum


class ResearchWorkspaceConsumerProjectionSectionChangeStatus(
    str,
    Enum,
):
    """
    Indicates how a specific logical section
    of a consumer projection changed between
    two fingerprint snapshots.

    Statuses:
    - UNCHANGED: Section fingerprints are identical
    - CHANGED: Section fingerprints differ (semantic content changed)
    - ADDED: Section exists in current but not in previous
    - REMOVED: Section existed in previous but not in current
    """

    UNCHANGED = "unchanged"

    CHANGED = "changed"

    ADDED = "added"

    REMOVED = "removed"
