from dataclasses import dataclass
from datetime import datetime

PREPARED = "PREPARED"
INVALIDATED = "INVALIDATED"
STATUSES = frozenset({PREPARED, INVALIDATED})


@dataclass(frozen=True)
class LLMCodePatchReleaseCandidate:
    """An immutable release candidate for an execution that has passed every
    Commit #11 gate.

    version is assigned once, at prepare() time, from the same job_id
    Commit #1's review already established, and never changes -- "immutable
    release version" means this field is fixed for the life of the
    candidate_id, not that the candidate can never be invalidated (see
    LLMCodePatchReleaseService.validate()). artifacts is a frozen
    {"job_id", "output"} snapshot of the exact CompilerJobResult.output
    (backend.compilation_execution, the only real build output this
    codebase has) that passed every gate at prepare() time -- a deep copy,
    so a later patch to the live generated output can never retroactively
    change what this candidate references. Preparing this candidate never
    mutates the gates, the execution, or the generated output, and this
    commit never deploys anything.
    """

    candidate_id: str
    execution_id: str
    version: str
    status: str
    artifacts: dict
    created_at: datetime
