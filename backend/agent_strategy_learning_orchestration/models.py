from dataclasses import dataclass
from datetime import datetime

# Plain string status vocabulary, the same convention
# backend.agent_memory_learning_orchestration's own
# PROCESSED/SKIPPED/FAILED already uses, rather than a new Enum type.
PROCESSED = "PROCESSED"
SKIPPED = "SKIPPED"
FAILED = "FAILED"
STATUSES = frozenset({PROCESSED, SKIPPED, FAILED})


@dataclass(frozen=True)
class LLMAgentStrategyLearningResult:
    """What one process_execution() call actually did.

    operations is the ordered, human-readable audit trail of every
    pipeline step attempted -- {"step", "outcome", "detail"} entries, in
    the order they ran -- the same shape
    backend.agent_memory_learning_orchestration.LLMAgentMemoryLearningResult
    already establishes, so the *actual operations performed* are always
    visible, not just the final status. A step never attempted (because
    an earlier one made it ineligible, or a per-strategy step failed for
    one strategy) simply has no entry for that strategy, rather than a
    fabricated one.

    outcomes/scores/lifecycle_decisions/audit_decisions are exactly what
    Commit #3 (via Commit #8)/#4/#9/#11 themselves produced -- nothing
    here recomputes or duplicates any of them, and every one preserves
    its own source strategy_id/execution_id, so the full strategy <->
    execution provenance survives in this one result. Each list holds
    only the strategies that successfully reached that step; a strategy
    whose own scoring/lifecycle/audit step failed is simply absent from
    the later lists, isolated from every other strategy's own result.

    status is PROCESSED once outcome recording (the pipeline's one
    all-or-nothing step) succeeded -- even if that means zero strategies
    were applied to learn from, or a later per-strategy step failed for
    some of them ("nothing to do", and "partial per-strategy failure",
    are both still a successful pipeline run, never a failure of the
    pipeline itself). SKIPPED means the execution was not eligible to
    process at all (still RUNNING, or already processed by an earlier
    call). FAILED means outcome recording itself raised, so no
    strategy's evidence could even be looked up.
    """

    execution_id: str
    status: str
    operations: list
    outcomes: list
    scores: list
    lifecycle_decisions: list
    audit_decisions: list
    processed_at: datetime
