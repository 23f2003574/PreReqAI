from datetime import datetime, timezone

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import LLMAgentLearningSignalExtractor
from backend.agent_memory_learning_updates import LLMAgentMemoryLearningUpdater
from backend.agent_memory_promotion import DEPRECATED, TRUSTED, LLMAgentMemoryPromoter
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.llm.tool_execution import RUNNING

from .models import FAILED, PROCESSED, SKIPPED, LLMAgentMemoryLearningResult


def _operation(step: str, outcome: str, detail: str) -> dict:
    return {"step": step, "outcome": outcome, "detail": detail}


class LLMAgentMemoryLearningOrchestrator:
    """Closes the learning loop: execution outcome -> signals -> memory
    update -> quality reassessment -> promotion/deprecation.

    Not a new workflow engine: every phase is an existing commit's own
    method, called unchanged --

        read execution outcome     Commit #12 (backend.agent_plan_execution)
                                    plan_execution_service.get()
        extract learning signals   Commit #8 signal_extractor.extract()/
                                    extract_for_memory()
        apply signals to memory    Commit #9 updater.apply_signals(), via
                                    its own update_from_execution() for
                                    process_execution()
        reassess quality           Commit #6 quality_assessor.assess()
        evaluate promotion         Commit #7 promoter.evaluate()/
                                    promote()/deprecate()

    This class holds no store of its own and introduces no new
    persistence: "persisting the resulting state" means actually calling
    Commit #9's apply_signals() and Commit #7's promote()/deprecate() --
    each already durable in its own existing way -- rather than a new
    subsystem doing so a second time.

    process_memory() is the full six-step pipeline; process_execution()
    is necessarily lighter -- there is no existing index from an
    execution_id back to whichever memory (if any) it relates to (the
    same honest limitation Commit #8's own extract() and Commit #9's own
    update_from_execution() already document), so it reads the execution
    and extracts execution-level signals, and stops there. Once a caller
    separately knows which memory_id an execution relates to,
    process_memory(memory_id) is how the rest of the pipeline runs.

    Each step is attempted only if the one before it succeeded, and a
    step's own failure is caught, recorded in the result's operations,
    and stops the pipeline there -- it is never allowed to propagate and
    mask what already happened, and no later step ever runs against
    inconsistent input. Nothing before the failing step is undone: every
    existing service call this orchestrator makes is already all-or-
    nothing on its own (Commit #9's apply_signals() validates every
    signal before applying any of them, for instance), so there is
    nothing partial to roll back -- a failure here only ever means later
    steps did not run, never that an earlier one's own effect was
    corrupted. An unknown memory_id/execution_id is not caught here: it
    propagates as the same UnknownAgentMemoryError/
    UnknownAgentPlanExecutionError every other commit already raises for
    it, since that is a caller error, not a mid-pipeline failure.

    promote() is only ever called when evaluate() finds a memory both
    eligible and not already TRUSTED -- calling process_memory() again
    with no new evidence re-evaluates but does not re-promote, so
    repeated processing stays idempotent rather than growing Commit #7's
    promotion history for no reason.
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        memory_service: LLMAgentMemoryService,
        signal_extractor: LLMAgentLearningSignalExtractor,
        updater: LLMAgentMemoryLearningUpdater,
        quality_assessor: LLMAgentMemoryQualityAssessor,
        promoter: LLMAgentMemoryPromoter,
    ):
        self._plan_execution_service = plan_execution_service
        self._memory_service = memory_service
        self._signal_extractor = signal_extractor
        self._updater = updater
        self._quality_assessor = quality_assessor
        self._promoter = promoter

    @staticmethod
    def _result(execution_id, memory_id, status, operations, signals, now, metadata=None, quality=None,
                decision=None, promotion_record=None) -> LLMAgentMemoryLearningResult:
        return LLMAgentMemoryLearningResult(
            execution_id=execution_id, memory_id=memory_id, status=status,
            operations=operations, signals=signals, metadata=metadata, quality=quality,
            promotion_decision=decision, promotion_record=promotion_record, processed_at=now,
        )

    def process_execution(self, execution_id: str, now: datetime = None) -> LLMAgentMemoryLearningResult:
        """Read execution_id's outcome and extract whatever execution-level
        learning signals it supports.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded by Commit #12 (propagated, not wrapped)
        """
        now = now or datetime.now(timezone.utc)
        execution = self._plan_execution_service.get(execution_id)
        operations = [_operation("read_execution", "ok", f"status={execution.status}")]

        if execution.status == RUNNING:
            operations.append(
                _operation("eligibility", "skipped", "execution has not completed yet")
            )
            return self._result(execution_id, None, SKIPPED, operations, [], now)

        try:
            update_result = self._updater.update_from_execution(execution_id, now=now)
        except Exception as error:
            operations.append(_operation("extract_signals", "error", str(error)))
            return self._result(execution_id, None, FAILED, operations, [], now)

        operations.append(
            _operation(
                "extract_signals", "ok",
                f"{len(update_result.signals)} execution-level signal(s) extracted",
            )
        )
        operations.append(
            _operation(
                "apply_signals", "skipped",
                "no memory is resolvable from an execution_id alone; call "
                "process_memory(memory_id) once one is known",
            )
        )
        return self._result(execution_id, None, PROCESSED, operations, update_result.signals, now)

    def process_memory(self, memory_id: str, now: datetime = None) -> LLMAgentMemoryLearningResult:
        """Run the full learning pipeline for memory_id: extract its
        current signals, apply them, reassess quality, and evaluate
        promotion/deprecation.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
        """
        now = now or datetime.now(timezone.utc)
        memory = self._memory_service.get(memory_id)
        operations = [_operation("read_memory", "ok", f"outcome={memory.outcome}")]

        try:
            signals = self._signal_extractor.extract_for_memory(memory_id, now=now)
        except Exception as error:
            operations.append(_operation("extract_signals", "error", str(error)))
            return self._result(memory.execution_id, memory_id, FAILED, operations, [], now)

        operations.append(_operation("extract_signals", "ok", f"{len(signals)} signal(s) extracted"))

        if not signals:
            operations.append(_operation("apply_signals", "skipped", "no learning evidence to apply"))
            return self._result(memory.execution_id, memory_id, PROCESSED, operations, signals, now)

        try:
            self._updater.apply_signals(memory_id, signals, now=now)
            metadata = self._updater.metadata_for(memory_id)
        except Exception as error:
            operations.append(_operation("apply_signals", "error", str(error)))
            return self._result(memory.execution_id, memory_id, FAILED, operations, signals, now)

        operations.append(
            _operation(
                "apply_signals", "ok",
                f"supporting={metadata.supporting_evidence_count} "
                f"contradicting={metadata.contradicting_evidence_count}",
            )
        )

        try:
            quality = self._quality_assessor.assess(memory_id, now=now)
        except Exception as error:
            operations.append(_operation("assess_quality", "error", str(error)))
            return self._result(memory.execution_id, memory_id, FAILED, operations, signals, now, metadata=metadata)

        operations.append(
            _operation(
                "assess_quality", "ok",
                f"quality_score={quality.quality_score:.3f} confidence={quality.confidence:.3f}",
            )
        )

        try:
            decision = self._promoter.evaluate(memory_id, now=now)
            promotion_record = None

            if decision.current_status == DEPRECATED:
                operations.append(_operation("promotion", "skipped", "memory is deprecated"))
            elif not decision.eligible:
                operations.append(_operation("promotion", "not_eligible", decision.reason))
            elif decision.current_status == TRUSTED:
                operations.append(_operation("promotion", "already_trusted", "no change"))
            else:
                promotion_record = self._promoter.promote(memory_id, now=now)
                operations.append(_operation("promotion", "promoted", decision.reason))
        except Exception as error:
            operations.append(_operation("promotion", "error", str(error)))
            return self._result(
                memory.execution_id, memory_id, FAILED, operations, signals, now,
                metadata=metadata, quality=quality,
            )

        return self._result(
            memory.execution_id, memory_id, PROCESSED, operations, signals, now,
            metadata=metadata, quality=quality, decision=decision, promotion_record=promotion_record,
        )
