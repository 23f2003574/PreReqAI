from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_feedback import MAX_RATING, MIN_RATING, LLMAgentMemoryFeedbackService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE
from backend.llm.tool_execution import FAILED, SUCCEEDED

from .models import (
    FAILED_STRATEGY,
    INCORRECT_KNOWLEDGE,
    REPEATED_FAILURE,
    REPEATED_SUCCESS,
    SUCCESSFUL_STRATEGY,
    USEFUL_KNOWLEDGE,
    LLMAgentLearningSignal,
)

# Which Commit #5 feedback_type maps to which knowledge signal. "useful"
# and "successful" both say the memory helped; "not_useful", "incorrect",
# and "failed" all say it did not -- the finer distinction those five
# types carry is preserved in the signal's own evidence (feedback_type),
# never discarded, just not re-split into more signal_types than the
# closed SIGNAL_TYPES vocabulary has room for.
_FEEDBACK_SIGNAL_TYPE = {
    "useful": USEFUL_KNOWLEDGE,
    "successful": USEFUL_KNOWLEDGE,
    "not_useful": INCORRECT_KNOWLEDGE,
    "incorrect": INCORRECT_KNOWLEDGE,
    "failed": INCORRECT_KNOWLEDGE,
}

# How favorably each feedback_type reads on its own, the same [MIN_SCORE,
# MAX_SCORE] scale as everything else here. Kept as its own local copy
# rather than importing Commit #6's private mapping -- the same
# "kept local" convention every secret-detection pattern in this
# repository already follows for a small, self-contained lookup.
_FEEDBACK_TYPE_VALUE = {
    "successful": MAX_SCORE,
    "useful": 0.75,
    "not_useful": 0.25,
    "incorrect": MIN_SCORE,
    "failed": MIN_SCORE,
}

# Two or more same-polarity signals is what "repeated" means here -- one
# occurrence is just that signal on its own, never inflated into a
# pattern by itself.
_REPEATED_THRESHOLD = 2


def _feedback_value(feedback) -> float:
    type_value = _FEEDBACK_TYPE_VALUE[feedback.feedback_type]
    if feedback.rating is None:
        return type_value
    normalized_rating = (feedback.rating - MIN_RATING) / (MAX_RATING - MIN_RATING)
    return round((type_value + normalized_rating) / 2, 6)


def _consolidation_sources(memory) -> list:
    """The Commit #4 "sources" a consolidated memory's content carries,
    or [] for an ordinary (never-consolidated) memory."""
    if isinstance(memory.content, dict) and memory.content.get("consolidated") is True:
        return memory.content.get("sources", [])
    return []


class LLMAgentLearningSignalExtractor:
    """Derives structured, evidence-traceable learning signals from a
    Commit #12 execution's outcome and a Commit #1 memory's Commit #5
    feedback history.

    Not a second evaluation or learning framework: every signal is read
    straight from an existing record -- LLMAgentPlanExecutionService.get()
    for an execution's own verified status, LLMAgentMemoryService.get()
    for a memory's own outcome, LLMAgentMemoryFeedbackService.
    list_for_memory() for its full feedback history, and (when present)
    Commit #4's own consolidated content["sources"] -- combined into one
    uniform LLMAgentLearningSignal shape rather than a new representation
    each caller has to interpret differently. No LLM call is made or
    needed, and nothing here is stored: extract()/extract_for_memory()
    only ever read, never write to any store, so calling either can never
    mutate a memory, its feedback, or its promotion status.

    A memory with genuinely contradictory feedback (some favorable, some
    not) yields both a useful_knowledge and an incorrect_knowledge signal
    -- and, once either side reaches _REPEATED_THRESHOLD, both a
    repeated_success and a repeated_failure signal too. Nothing here picks
    a winner or averages them into one verdict; every signal the evidence
    supports is returned, and it is left to a later consumer (not this
    commit) to weigh them.
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        memory_service: LLMAgentMemoryService,
        feedback_service: LLMAgentMemoryFeedbackService,
    ):
        self._plan_execution_service = plan_execution_service
        self._memory_service = memory_service
        self._feedback_service = feedback_service

    def extract(self, execution_id: str, now: datetime = None) -> list:
        """Signals derivable from execution_id's own verified outcome alone.

        No memory lookup is attempted here -- there is no existing index
        from an execution_id back to whichever memory (if any) it
        produced -- so every signal returned has memory_id=None.
        RUNNING/REJECTED/CANCELLED carry no strategy verdict to report, so
        extract() returns [] for any of them rather than guessing one.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded by Commit #12 (propagated, not wrapped)
        """
        execution = self._plan_execution_service.get(execution_id)
        now = now or datetime.now(timezone.utc)

        if execution.status not in (SUCCEEDED, FAILED):
            return []

        return [self._strategy_signal(execution_id, execution.status, memory_id=None, now=now)]

    def extract_for_memory(self, memory_id: str, now: datetime = None) -> list:
        """Every signal derivable from memory_id: its own outcome, one
        signal per feedback record ever given for it, and any
        repeated-pattern signal either of those supports.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        memory = self._memory_service.get(memory_id)
        feedback_records = self._feedback_service.list_for_memory(memory_id)
        now = now or datetime.now(timezone.utc)

        signals = [self._strategy_signal(memory.execution_id, memory.outcome, memory_id, now)]
        signals.extend(self._feedback_signals(memory_id, feedback_records, now))
        signals.extend(self._repeated_feedback_signals(memory_id, feedback_records, now))
        signals.extend(self._repeated_consolidation_signals(memory, now))
        return signals

    @staticmethod
    def _strategy_signal(execution_id: str, status: str, memory_id, now: datetime) -> LLMAgentLearningSignal:
        is_success = status == SUCCEEDED
        return LLMAgentLearningSignal(
            execution_id=execution_id,
            memory_id=memory_id,
            signal_type=SUCCESSFUL_STRATEGY if is_success else FAILED_STRATEGY,
            value=MAX_SCORE if is_success else MIN_SCORE,
            evidence={"source": "execution", "execution_id": execution_id, "status": status},
            created_at=now,
        )

    @staticmethod
    def _feedback_signals(memory_id: str, feedback_records: list, now: datetime) -> list:
        return [
            LLMAgentLearningSignal(
                execution_id=feedback.execution_id,
                memory_id=memory_id,
                signal_type=_FEEDBACK_SIGNAL_TYPE[feedback.feedback_type],
                value=_feedback_value(feedback),
                evidence={
                    "source": "feedback",
                    "feedback_id": feedback.feedback_id,
                    "feedback_type": feedback.feedback_type,
                    "rating": feedback.rating,
                },
                created_at=now,
            )
            for feedback in feedback_records
        ]

    @staticmethod
    def _repeated_feedback_signals(memory_id: str, feedback_records: list, now: datetime) -> list:
        favorable = [f for f in feedback_records if _FEEDBACK_SIGNAL_TYPE[f.feedback_type] == USEFUL_KNOWLEDGE]
        unfavorable = [f for f in feedback_records if _FEEDBACK_SIGNAL_TYPE[f.feedback_type] == INCORRECT_KNOWLEDGE]

        signals = []
        if len(favorable) >= _REPEATED_THRESHOLD:
            signals.append(
                LLMAgentLearningSignal(
                    execution_id=favorable[-1].execution_id,
                    memory_id=memory_id,
                    signal_type=REPEATED_SUCCESS,
                    value=round(sum(_feedback_value(f) for f in favorable) / len(favorable), 6),
                    evidence={
                        "source": "feedback_repeated",
                        "feedback_ids": [f.feedback_id for f in favorable],
                        "count": len(favorable),
                    },
                    created_at=now,
                )
            )
        if len(unfavorable) >= _REPEATED_THRESHOLD:
            signals.append(
                LLMAgentLearningSignal(
                    execution_id=unfavorable[-1].execution_id,
                    memory_id=memory_id,
                    signal_type=REPEATED_FAILURE,
                    value=round(sum(_feedback_value(f) for f in unfavorable) / len(unfavorable), 6),
                    evidence={
                        "source": "feedback_repeated",
                        "feedback_ids": [f.feedback_id for f in unfavorable],
                        "count": len(unfavorable),
                    },
                    created_at=now,
                )
            )
        return signals

    @staticmethod
    def _repeated_consolidation_signals(memory, now: datetime) -> list:
        sources = _consolidation_sources(memory)
        if not sources:
            return []

        succeeded = [source for source in sources if source.get("outcome") == SUCCEEDED]
        failed = [source for source in sources if source.get("outcome") != SUCCEEDED]

        signals = []
        if len(succeeded) >= _REPEATED_THRESHOLD:
            signals.append(
                LLMAgentLearningSignal(
                    execution_id=memory.execution_id,
                    memory_id=memory.memory_id,
                    signal_type=REPEATED_SUCCESS,
                    value=MAX_SCORE,
                    evidence={
                        "source": "consolidation",
                        "source_memory_ids": [source["memory_id"] for source in succeeded],
                        "count": len(succeeded),
                    },
                    created_at=now,
                )
            )
        if len(failed) >= _REPEATED_THRESHOLD:
            signals.append(
                LLMAgentLearningSignal(
                    execution_id=memory.execution_id,
                    memory_id=memory.memory_id,
                    signal_type=REPEATED_FAILURE,
                    value=MIN_SCORE,
                    evidence={
                        "source": "consolidation",
                        "source_memory_ids": [source["memory_id"] for source in failed],
                        "count": len(failed),
                    },
                    created_at=now,
                )
            )
        return signals
