from dataclasses import dataclass
from datetime import datetime
from typing import Optional

PREPARED = "PREPARED"
RELEASED = "RELEASED"
STATUSES = frozenset({PREPARED, RELEASED})


@dataclass(frozen=True)
class LLMTransformationRelease:
    """One immutable release candidate for an execution that has passed
    every Commit #11 gate.

    version is assigned once, at prepare() time, and never changes --
    "immutable release version" means this field is fixed for the life of
    the release_id, not that the record itself can never move from
    PREPARED to RELEASED (see LLMTransformationReleaseService.release()).
    released_at is None until release() actually promotes this candidate;
    prepare()/validate() never mutate notebook source, the gates, or
    anything upstream of it, and release() never deploys anything.
    """

    release_id: str
    execution_id: str
    version: str
    status: str
    released_at: Optional[datetime]
