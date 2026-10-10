from enum import (
    Enum,
)


class ResearchSnapshotImportStrategy(
    str,
    Enum,
):
    """
    Defines how snapshot identity conflicts
    are handled during import planning.
    """

    REJECT = (
        "reject"
    )

    REMAP_CONFLICTS = (
        "remap_conflicts"
    )

    REMAP_ALL = (
        "remap_all"
    )
