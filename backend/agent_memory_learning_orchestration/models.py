from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Plain string status vocabulary, the same convention
# backend.llm.tool_execution's SUCCEEDED/FAILED and
# backend.agent_memory_promotion's CANDIDATE/TRUSTED/DEPRECATED already
# use, rather than a new Enum type.
PROCESSED = "PROCESSED"
SKIPPED = "SKIPPED"
FAILED = "FAILED"
STATUSES = frozenset({PROCESSED, SKIPPED, FAILED})


@dataclass(frozen=True)
class LLMAgentMemoryLearningResult:
    """What one process_execution()/process_memory() call actually did.

    operations is the ordered, human-readable audit trail of every
    pipeline step attempted -- {"step", "outcome", "detail"} entries, in
    the order they ran -- so the *actual operations performed* are always
    visible, not just the final status. A step never attempted (because
    an earlier one was ineligible or failed) simply has no entry, rather
    than a fabricated one.

    signals/metadata/quality/promotion_decision/promotion_record are
    exactly what Commit #8/#9/#6/#7 themselves produced -- nothing here
    recomputes or duplicates any of them, and every one preserves its own
    source execution_id/feedback_id/memory_id, so the full source
    execution/signal/feedback relationship survives in this one result.
    Each is None only when the pipeline never reached that step (SKIPPED
    or FAILED before it, or -- for process_execution() -- no memory was
    ever resolvable to apply signals to in the first place).

    status is PROCESSED once every step the pipeline could reach
    completed without error (even if that means zero signals existed to
    apply -- "nothing to do" is still a successful outcome, not a
    failure), SKIPPED when the execution/memory was not eligible to
    process at all, and FAILED when some step raised and processing
    stopped there. FAILED never means memory_id's own record, its
    feedback, or any promotion history recorded before this call was
    corrupted -- every step already only ever appends or reads, per
    Commit #1/#5/#6/#7/#9's own conventions, so a mid-pipeline failure
    simply means later steps never ran.
    """

    execution_id: Optional[str]
    memory_id: Optional[str]
    status: str
    operations: list
    signals: list
    metadata: Optional[object]
    quality: Optional[object]
    promotion_decision: Optional[object]
    promotion_record: Optional[object]
    processed_at: datetime
