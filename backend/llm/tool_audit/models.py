from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..tool_execution import STATUSES as EXECUTION_STATUSES
from ..tool_permissions import AUTHORIZED, CONDITIONAL, DENIED

# The one state that is this trail's own: a plan has been recorded but
# nothing has been authorized or run against it yet. Every other status is
# borrowed from the service that actually decides it -- Commit #4's
# authorization decisions and Commit #5's execution statuses -- so the audit
# trail never invents a vocabulary that could drift from the facts it
# records.
PLANNED = "PLANNED"
STATUSES = frozenset({PLANNED, AUTHORIZED, CONDITIONAL, DENIED}) | EXECUTION_STATUSES


@dataclass(frozen=True)
class LLMToolAudit:
    """One immutable snapshot of a tool invocation's lifecycle.

    Follows the append-only convention of the codebase's existing audit
    trails (LLMRequestAudit, LLMTransformationAudit): a snapshot is never
    mutated or replaced in place. Each lifecycle event -- start,
    authorization, execution, completion -- appends a new snapshot, so
    history() is a genuine trail rather than a running total.

    The three identifiers chain the lifecycle together: request_id is the
    conversation (Commit #7) the call came from, plan_id the validated
    invocation plan (Commit #3), execution_id the attempt to run it
    (Commit #5). execution_id is None for snapshots taken before an
    execution existed.

    What is deliberately absent: the tool's arguments and its output.
    Either can carry credentials, and neither is needed to reconstruct who
    asked for what, when, and how it was decided. subject and reason are
    passed through the codebase's secret-redaction check before they are
    stored.
    """

    audit_id: str
    request_id: str
    plan_id: str
    execution_id: Optional[str]
    tool_name: str
    subject: Optional[str]
    status: str
    authorization: Optional[str] = None
    authorization_policy_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
