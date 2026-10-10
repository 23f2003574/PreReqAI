from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionFreshnessSummary:
    """
    Compact summary of source freshness classifications.

    Summarizes the final freshness classifications of source
    observations relevant to the projection execution.

    Does not duplicate source details such as every source key,
    timestamp, age calculation, or threshold. Those belong to the
    full freshness/resolution metadata.

    Attributes:
        observed_source_count: Total number of sources observed
        fresh_source_count: Number of sources with FRESH status
        stale_usable_source_count: Number of sources with STALE status
        expired_source_count: Number of sources with UNUSABLE status
        unknown_source_count: Number of sources without classification
    """

    observed_source_count: int

    fresh_source_count: int

    stale_usable_source_count: int

    expired_source_count: int

    unknown_source_count: int
