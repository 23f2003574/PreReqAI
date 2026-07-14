from enum import Enum


class ResearchWorkspaceConsumerProjectionChangeStatus(
    str,
    Enum,
):
    """
    Indicates whether two consumer projection
    fingerprint snapshots represent identical
    or different semantic state.

    Statuses:
    - UNCHANGED: Semantic fingerprints match exactly
    - CHANGED: Semantic fingerprints differ
    - INCOMPARABLE: Snapshots cannot be safely compared
      (e.g., different projection types, incompatible versions)
    """

    UNCHANGED = "unchanged"

    CHANGED = "changed"

    INCOMPARABLE = "incomparable"
