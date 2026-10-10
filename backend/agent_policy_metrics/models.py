from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyMetrics:
    """Read-only aggregate counts over Commit #7's own audit trail for
    one scope (and, optionally, one set of filters) -- never a source of
    truth in its own right, and never written back anywhere.

    total/allowed/denied are record counts; exception_assisted counts
    records whose Commit #7 exceptions list was non-empty (a Commit #5
    exception actually contributed to the outcome). denial_rate is
    denied/total, 0.0 when total is 0 rather than a division error -- an
    empty dataset is a valid, complete answer, not a failure (see Rules:
    "Handle empty datasets cleanly").

    by_policy/by_rule break the same {total, allowed, denied} shape down
    by every policy_id/rule_id named in the aggregated records'
    matched_rules -- a record's own overall decision is attributed to
    every policy/rule that had a matched rule within it, so a policy's
    own bucket always answers "how many decisions did this policy
    participate in, and how did they turn out overall". by_period
    breaks the same shape down by the UTC calendar day each record was
    created on. Unlike a closed vocabulary (ALLOW/DENY), policy/rule/day
    identifiers are open-ended, so these three mappings only ever contain
    the keys the aggregated records actually named -- never a
    pre-populated, zero-valued entry for an identifier nothing
    mentioned.
    """

    scope_id: str
    total: int
    allowed: int
    denied: int
    exception_assisted: int
    denial_rate: float
    by_policy: dict
    by_rule: dict
    by_period: dict
