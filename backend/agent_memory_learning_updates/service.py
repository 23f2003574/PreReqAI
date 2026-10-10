from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import LLMAgentLearningSignalExtractor
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE

from .models import LLMAgentMemoryLearningMetadata, LLMAgentMemoryLearningUpdateResult

# The midpoint of the repository's own [MIN_SCORE, MAX_SCORE] signal-value
# scale: a signal at or above it is supporting evidence, below it is
# contradicting -- the same >= convention Commit #6's own agreement-factor
# computation uses.
_FAVORABLE_THRESHOLD = (MIN_SCORE + MAX_SCORE) / 2

# Commit #8's own signal_type/evidence["source"] vocabulary. repeated_*
# signals and consolidation-derived signals summarize other, more atomic
# signals (feedback/execution records) that are *also* present in the
# same extract_for_memory() result -- counting them here too would double
# count the same underlying evidence, so only atomic sources are ever
# tallied.
_ATOMIC_SOURCES = frozenset({"execution", "feedback"})

# Of the atomic sources, only "feedback" reflects an actual later reuse
# of the memory -- "execution" is the memory's own origin, not a "use" of
# it -- so successful_use_count/failed_use_count only ever count feedback.
_USE_SOURCES = frozenset({"feedback"})

_EMPTY_METADATA_KWARGS = dict(
    supporting_evidence_count=0, contradicting_evidence_count=0,
    successful_use_count=0, failed_use_count=0, evidence_refs=(), last_updated_at=None,
)


class MismatchedSignalError(ValueError):
    """Raised when apply_signals() is given a signal that is not actually
    traceable to memory_id -- its own memory_id names a different memory,
    or (for a memory_id=None execution-level signal) its evidence's own
    execution_id does not match memory_id's origin execution.
    """


def _evidence_ref(signal) -> tuple:
    """The (source, identity) pair that makes one signal's underlying
    evidence uniquely identifiable, for idempotent counting."""
    evidence = signal.evidence
    identity = evidence.get("feedback_id") or evidence.get("execution_id")
    return (evidence.get("source"), identity)


class LLMAgentMemoryLearningUpdater:
    """Accumulates Commit #8 learning signals into an evidence-backed
    tally for a Commit #1 memory, without ever rewriting the memory's own
    content.

    Not a second memory-state system: signals are Commit #8's own
    LLMAgentLearningSignal, produced by its own
    LLMAgentLearningSignalExtractor (extract()/extract_for_memory()) --
    this service adds no new way to derive one. Tracking itself is a
    single plain in-process dict of running totals, the same "service
    holds its own small internal state" pattern
    backend.agent_execution_budget.LLMAgentExecutionBudgetService already
    uses for its own usage/limits, not a new persistence subsystem: there
    is no store, no ABC, no file format, and restarting the process
    forgets it, exactly as backend.agent_execution_budget's own usage
    does. What actually persists -- the memory itself, its feedback, its
    promotion history -- is unchanged by any of this.

    apply_signals() never calls Commit #1's record()/store.save(): the
    underlying LLMAgentMemory this returns is read via get() and handed
    back exactly as stored, never modified. Reapplying the exact same
    signal (the same underlying feedback_id/execution_id, whether within
    one call's list or across separate calls) is a no-op the second time:
    each piece of evidence is counted into the tally at most once, tracked
    by evidence_refs.

    quality_for()/promotion_decision_for() delegate straight to Commit
    #6/#7 -- both already read the same underlying memory/feedback/
    consolidation records this service's own signals are drawn from, so
    "feeding updated evidence into them" means calling them, never
    re-scoring anything here a second way.
    """

    def __init__(
        self,
        memory_service: LLMAgentMemoryService,
        signal_extractor: LLMAgentLearningSignalExtractor,
        quality_assessor=None,
        promoter=None,
    ):
        self._memory_service = memory_service
        self._signal_extractor = signal_extractor
        self._quality_assessor = quality_assessor
        self._promoter = promoter
        self._metadata_by_memory = {}

    @staticmethod
    def _validate_signal(memory, signal):
        if signal.memory_id is not None:
            if signal.memory_id != memory.memory_id:
                raise MismatchedSignalError(
                    f"signal is for memory {signal.memory_id!r}, not {memory.memory_id!r}"
                )
            return

        # A memory_id=None signal is only ever traceable to memory_id if
        # it is that memory's own origin execution's signal.
        if signal.evidence.get("execution_id") != memory.execution_id:
            raise MismatchedSignalError(
                f"signal for execution {signal.evidence.get('execution_id')!r} is not traceable "
                f"to memory {memory.memory_id!r} (origin execution {memory.execution_id!r})"
            )

    def apply_signals(self, memory_id: str, signals: list, now: datetime = None):
        """Fold `signals` into memory_id's running learning tally and
        return the memory, untouched.

        Every signal must be traceable to memory_id (see
        _validate_signal()) or this raises before anything is applied --
        a partially-applied update never happens. A repeated_*/
        consolidation-derived signal is accepted but contributes nothing
        of its own: it summarizes atomic (execution/feedback) signals
        that are counted directly, so counting it too would double-count
        the same evidence.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
            MismatchedSignalError: If any signal is not traceable to
                memory_id
        """
        memory = self._memory_service.get(memory_id)
        now = now or datetime.now(timezone.utc)

        for signal in signals:
            self._validate_signal(memory, signal)

        current = self._metadata_by_memory.get(memory_id)
        if current is None:
            current = LLMAgentMemoryLearningMetadata(memory_id=memory_id, **_EMPTY_METADATA_KWARGS)

        supporting = current.supporting_evidence_count
        contradicting = current.contradicting_evidence_count
        successful_use = current.successful_use_count
        failed_use = current.failed_use_count
        seen = set(current.evidence_refs)
        applied_new = False

        for signal in signals:
            source = signal.evidence.get("source")
            if source not in _ATOMIC_SOURCES:
                continue

            ref = _evidence_ref(signal)
            if ref in seen:
                continue
            seen.add(ref)
            applied_new = True

            favorable = signal.value >= _FAVORABLE_THRESHOLD
            if favorable:
                supporting += 1
            else:
                contradicting += 1

            if source in _USE_SOURCES:
                if favorable:
                    successful_use += 1
                else:
                    failed_use += 1

        last_updated_at = now if applied_new else current.last_updated_at

        self._metadata_by_memory[memory_id] = LLMAgentMemoryLearningMetadata(
            memory_id=memory_id,
            supporting_evidence_count=supporting,
            contradicting_evidence_count=contradicting,
            successful_use_count=successful_use,
            failed_use_count=failed_use,
            evidence_refs=tuple(sorted(seen, key=str)),
            last_updated_at=last_updated_at,
        )
        return memory

    def metadata_for(self, memory_id: str) -> LLMAgentMemoryLearningMetadata:
        """memory_id's current tally, or an all-zero one if apply_signals()
        has never been called for it.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        self._memory_service.get(memory_id)
        return self._metadata_by_memory.get(memory_id) or LLMAgentMemoryLearningMetadata(
            memory_id=memory_id, **_EMPTY_METADATA_KWARGS
        )

    def update_from_memory(self, memory_id: str, now: datetime = None):
        """Re-extract memory_id's complete current signal set (Commit #8's
        own extract_for_memory()) and apply_signals() it -- the common
        "refresh from everything on record" call."""
        now = now or datetime.now(timezone.utc)
        signals = self._signal_extractor.extract_for_memory(memory_id, now=now)
        return self.apply_signals(memory_id, signals, now=now)

    def update_from_execution(self, execution_id: str, now: datetime = None) -> LLMAgentMemoryLearningUpdateResult:
        """Execution-level learning result for execution_id: Commit #8's
        own extract(execution_id), reported as-is.

        There is no existing index from an execution_id back to whichever
        memory (if any) it produced or relates to, so memory_id and
        metadata are always None here -- the same honest limitation
        Commit #8's own extract() carries. Once a caller separately knows
        which memory_id an execution relates to, apply_signals() or
        update_from_memory() is how the resulting signals actually get
        applied.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded by Commit #12 (propagated, not wrapped)
        """
        now = now or datetime.now(timezone.utc)
        signals = self._signal_extractor.extract(execution_id, now=now)
        return LLMAgentMemoryLearningUpdateResult(
            execution_id=execution_id, memory_id=None, signals=signals, metadata=None, updated_at=now,
        )

    def quality_for(self, memory_id: str, now: datetime = None):
        """memory_id's current Commit #6 quality assessment, or None if
        this updater was built without a quality_assessor. Delegates
        entirely -- never a second scoring implementation."""
        if self._quality_assessor is None:
            return None
        return self._quality_assessor.assess(memory_id, now=now)

    def promotion_decision_for(self, memory_id: str, now: datetime = None):
        """memory_id's current Commit #7 promotion decision, or None if
        this updater was built without a promoter. Delegates entirely --
        never a second promotion implementation."""
        if self._promoter is None:
            return None
        return self._promoter.evaluate(memory_id, now=now)
