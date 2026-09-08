from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryCheck:
    """can_recover()'s pure, read-only judgment for one execution_id --
    never itself a mutation, and reused verbatim by recover() so the two
    methods can never disagree about whether an execution is eligible.

    status is the execution's own current status at the moment of the
    check (Commit #7's own RUNNING/SUCCEEDED/FAILED vocabulary, reused
    as-is). reason is always populated, whether recoverable is True or
    False -- the same "never silently imply a decision" discipline every
    other *Result/*Check in this series already keeps.
    """

    recoverable: bool
    execution_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class CapabilityRecoveryResult:
    """recover()'s complete outcome for one execution_id.

    previous_status/new_status are equal whenever recover() did not
    (or, being non-recoverable, could not) change anything -- a real
    transition only ever happens for a RUNNING execution being closed
    out as FAILED; a retryable FAILED execution is reported recoverable
    without any mutation, since Commit #7's own service refuses to
    reopen a terminal record by design (Rule: "preserve the original
    execution record and provenance" -- there is nothing this service
    could safely change on an already-terminal record, so it changes
    nothing).
    """

    recoverable: bool
    execution_id: str
    previous_status: str
    new_status: str
    reason: str
