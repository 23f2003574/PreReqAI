from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor

from .in_memory_store import InMemoryLLMAgentMemoryPromotionStore
from .models import (
    CANDIDATE,
    DEPRECATED,
    MIN_TRUSTED_CONFIDENCE,
    MIN_TRUSTED_QUALITY,
    STATUSES,
    TRUSTED,
    LLMAgentMemoryPromotionDecision,
    LLMAgentMemoryPromotionRecord,
)
from .store import LLMAgentMemoryPromotionStore


class InvalidPromotionStatusError(ValueError):
    """Raised when a status argument is not one of STATUSES."""


class InsufficientEvidenceError(ValueError):
    """Raised when promote() is refused because the memory's current
    Commit #6 quality/confidence does not meet the trusted threshold."""


class InvalidPromotionTransitionError(ValueError):
    """Raised when promote() is refused because of the memory's current
    status -- specifically, a DEPRECATED memory cannot be promoted
    straight back to trusted. Deprecation is a deliberate, explicit
    decision; reversing it is not automatic (no learning loop exists yet
    to decide that on its own), so it is refused rather than silently
    re-trusting a memory someone previously flagged as unreliable.
    """


class LLMAgentMemoryPromoter:
    """Identifies high-quality Commit #1 memories and marks them trusted,
    reusable knowledge for future agent executions.

    Not a second knowledge-management system: eligibility is entirely
    Commit #6's own LLMAgentMemoryQualityAssessor.assess() -- quality_score
    and confidence, which already fold in the memory's own execution
    outcome, every Commit #5 feedback record (successful/negative/
    contradictory), and Commit #4 consolidation history. This service adds
    only a status on top of that judgment: CANDIDATE, TRUSTED, or
    DEPRECATED, recorded as an append-only
    LLMAgentMemoryPromotionRecord history (the same shape Commit #5's own
    feedback history uses) rather than a field mutated on the memory
    itself. A memory with no promotion record at all is CANDIDATE by
    convention -- new memories begin as candidates without requiring an
    explicit record for every single one Commit #1 ever creates.

    promote()/deprecate() never call Commit #1's record()/store.save():
    the underlying LLMAgentMemory (content, execution_id, outcome,
    created_at) is never mutated by a status change, and deprecate()
    never removes anything -- a deprecated memory, and its full history,
    stays exactly as reachable through Commit #1's get()/list() as any
    other.
    """

    def __init__(
        self,
        memory_service: LLMAgentMemoryService,
        quality_assessor: LLMAgentMemoryQualityAssessor,
        store: LLMAgentMemoryPromotionStore = None,
    ):
        self._memory_service = memory_service
        self._quality_assessor = quality_assessor
        self.store = store if store is not None else InMemoryLLMAgentMemoryPromotionStore()

    def status_for(self, memory_id: str) -> str:
        """memory_id's current status: the most recent promotion record's
        status, or CANDIDATE if none has ever been recorded.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        self._memory_service.get(memory_id)
        history = self.store.list_for_memory(memory_id)
        return history[-1].status if history else CANDIDATE

    def evaluate(self, memory_id: str, now: datetime = None) -> LLMAgentMemoryPromotionDecision:
        """What promote() would decide for memory_id right now, without
        applying it -- evaluate() never appends a promotion record.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        now = now or datetime.now(timezone.utc)
        current_status = self.status_for(memory_id)
        quality = self._quality_assessor.assess(memory_id, now=now)

        if current_status == DEPRECATED:
            return LLMAgentMemoryPromotionDecision(
                memory_id=memory_id, current_status=current_status, recommended_status=DEPRECATED,
                eligible=False,
                reason="memory is deprecated; promotion requires an explicit re-instatement this "
                       "service does not perform automatically",
                quality_score=quality.quality_score, confidence=quality.confidence, evaluated_at=now,
            )

        meets_quality = quality.quality_score >= MIN_TRUSTED_QUALITY
        meets_confidence = quality.confidence >= MIN_TRUSTED_CONFIDENCE
        eligible = meets_quality and meets_confidence

        if eligible:
            reason = (
                f"quality_score={quality.quality_score:.3f} >= {MIN_TRUSTED_QUALITY} and "
                f"confidence={quality.confidence:.3f} >= {MIN_TRUSTED_CONFIDENCE}"
            )
        else:
            shortfalls = []
            if not meets_quality:
                shortfalls.append(f"quality_score={quality.quality_score:.3f} < {MIN_TRUSTED_QUALITY}")
            if not meets_confidence:
                shortfalls.append(f"confidence={quality.confidence:.3f} < {MIN_TRUSTED_CONFIDENCE}")
            reason = "; ".join(shortfalls) + f" ({quality.assessment_reason})"

        return LLMAgentMemoryPromotionDecision(
            memory_id=memory_id, current_status=current_status,
            recommended_status=TRUSTED if eligible else CANDIDATE,
            eligible=eligible, reason=reason,
            quality_score=quality.quality_score, confidence=quality.confidence, evaluated_at=now,
        )

    def promote(self, memory_id: str, now: datetime = None) -> LLMAgentMemoryPromotionRecord:
        """Mark memory_id trusted, if evaluate() finds it currently eligible.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
            InvalidPromotionTransitionError: If memory_id is currently
                DEPRECATED
            InsufficientEvidenceError: If its quality_score or confidence
                falls short of the trusted threshold
        """
        decision = self.evaluate(memory_id, now=now)

        if decision.current_status == DEPRECATED:
            raise InvalidPromotionTransitionError(decision.reason)
        if not decision.eligible:
            raise InsufficientEvidenceError(decision.reason)

        record = LLMAgentMemoryPromotionRecord(
            memory_id=memory_id, status=TRUSTED, reason=decision.reason,
            quality_score=decision.quality_score, confidence=decision.confidence,
            decided_at=decision.evaluated_at,
        )
        return self.store.save(record)

    def deprecate(self, memory_id: str, reason: str, now: datetime = None) -> LLMAgentMemoryPromotionRecord:
        """Mark memory_id deprecated, from any current status, always with
        an explicit reason. Never deletes memory_id or any of its history --
        only appends this decision alongside it.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
            ValueError: If reason is empty or not a string
        """
        self._memory_service.get(memory_id)
        if not reason or not isinstance(reason, str):
            raise ValueError("reason is required to deprecate a memory")

        now = now or datetime.now(timezone.utc)
        quality = self._quality_assessor.assess(memory_id, now=now)

        record = LLMAgentMemoryPromotionRecord(
            memory_id=memory_id, status=DEPRECATED, reason=reason,
            quality_score=quality.quality_score, confidence=quality.confidence, decided_at=now,
        )
        return self.store.save(record)

    def history(self, memory_id: str) -> list:
        """Every promotion/deprecation decision ever recorded for memory_id,
        oldest first -- the complete lifecycle trail, never collapsed to
        just the current status."""
        return self.store.list_for_memory(memory_id)

    def list_for_scope(self, scope_id: str, status: str = None) -> list:
        """Every memory in scope_id, optionally filtered to one status --
        so a retrieval caller can distinguish trusted memories from
        candidates (or deprecated ones). Delegates listing itself entirely
        to Commit #1's own LLMAgentMemoryService.list(scope_id): this adds
        no isolation logic of its own, and never reads memory belonging to
        any other scope.
        """
        memories = self._memory_service.list(scope_id)
        if status is None:
            return memories
        if status not in STATUSES:
            raise InvalidPromotionStatusError(f"status {status!r} is not one of {sorted(STATUSES)}")
        return [memory for memory in memories if self.status_for(memory.memory_id) == status]
