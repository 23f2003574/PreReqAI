from enum import Enum


class ResearchSessionKind(
    str,
    Enum,
):
    """
    Describes whether a research session
    is a lineage root or a derived branch.
    """

    ROOT = "root"

    BRANCH = "branch"
