from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# The kinds of structured, evidence-backed conclusion extraction can draw.
# Deliberately small and closed, the same reasoning
# backend.agent_execution_memory.VALID_MEMORY_TYPES and
# backend.agent_memory_feedback.VALID_FEEDBACK_TYPES already document.
#
# successful_strategy/failed_strategy come only from a plan execution's
# own verified Commit #12 status -- never from feedback, which Commit #5
# deliberately does not treat as truth. useful_knowledge/incorrect_knowledge
# come only from Commit #5 feedback about a memory's reuse. repeated_success/
# repeated_failure summarize two or more same-polarity signals of either
# kind (feedback agreement, or Commit #4 consolidated source outcomes)
# with the same threshold, so this closed vocabulary intentionally keeps
# "one occurrence" and "a pattern" distinguishable.
SUCCESSFUL_STRATEGY = "successful_strategy"
FAILED_STRATEGY = "failed_strategy"
USEFUL_KNOWLEDGE = "useful_knowledge"
INCORRECT_KNOWLEDGE = "incorrect_knowledge"
REPEATED_SUCCESS = "repeated_success"
REPEATED_FAILURE = "repeated_failure"
SIGNAL_TYPES = frozenset(
    {
        SUCCESSFUL_STRATEGY,
        FAILED_STRATEGY,
        USEFUL_KNOWLEDGE,
        INCORRECT_KNOWLEDGE,
        REPEATED_SUCCESS,
        REPEATED_FAILURE,
    }
)


@dataclass(frozen=True)
class LLMAgentLearningSignal:
    """One structured, evidence-traceable conclusion drawn from an
    execution's outcome or a memory's feedback history.

    Purely derived, never a new fact: `evidence` always names exactly the
    concrete record(s) (an execution_id and its Commit #12 status, or one
    or more Commit #5 feedback_ids and their feedback_type/rating) the
    signal was read from, so every signal is traceable back to something
    that actually happened -- nothing here is invented or inferred beyond
    what that evidence directly supports. value is on the same
    [MIN_SCORE, MAX_SCORE] 0.0-1.0 scale backend.llm.evaluation_scoring
    and Commit #6's quality assessment already use.

    memory_id is None for a signal LLMAgentLearningSignalExtractor.extract()
    derives from an execution alone, with no memory lookup involved; it is
    always set for a signal extract_for_memory() derives.

    Nothing about extracting a signal ever writes to any store -- this is
    a value object, produced fresh on each call, never persisted or
    reused across calls the way Commit #1's memory or Commit #5's
    feedback are.
    """

    execution_id: str
    signal_type: str
    value: float
    evidence: dict
    memory_id: Optional[str] = None
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
