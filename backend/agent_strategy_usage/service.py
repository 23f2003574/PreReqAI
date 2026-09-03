from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_strategy_library import LLMAgentStrategyService

from .in_memory_store import InMemoryLLMAgentStrategyUsageStore
from .models import MAX_SELECTION_SCORE, MIN_SELECTION_SCORE, LLMAgentStrategyUsage
from .store import LLMAgentStrategyUsageStore


class UnknownAgentStrategyUsageError(KeyError):
    """Raised when get() is given a usage_id that was never recorded."""


class InvalidSelectionScoreError(ValueError):
    """Raised when selection_score is not a number in [MIN_SELECTION_SCORE, MAX_SELECTION_SCORE]."""


class InvalidAppliedFlagError(ValueError):
    """Raised when applied is not a bool."""


class LLMAgentStrategyUsageService:
    """Records that a Commit #1 strategy was selected -- and, separately,
    whether it was actually applied -- for a real execution, closing the
    gap between Commit #5/#6's own selection/application and measurable
    real-world usage.

    Not a second execution-analytics system: persistence is the same
    save/get/list_for_ split
    backend.agent_strategy_effectiveness.LLMAgentStrategyOutcomeService
    already uses (an InMemoryLLMAgentStrategyUsageStore by default, or the
    JSON-file-backed store built on the same backend.storage.AtomicJsonFile
    every other module here uses). record() never takes strategy_id or
    execution_id on faith: it reads Commit #1's own
    LLMAgentStrategyService.get(strategy_id) and the real
    LLMAgentPlanExecutionService.get(execution_id), each propagating that
    service's own "unknown" error unchanged rather than a usage-specific
    wrapper. Neither call ever mutates what it reads.

    Unlike Commit #3's own outcome recording, record() does not require
    execution_id to be terminal: usage marks that a strategy was part of
    the plan behind an execution, a fact that is already true the moment
    that execution exists, well before (or regardless of) how it turns
    out -- judging how it turned out stays entirely Commit #3/#4's job.
    Nothing here scores, ranks, or otherwise judges effectiveness; a usage
    record is raw evidence a later commit (Commit #8) can consume, never
    a verdict this service forms on its own.

    record() is idempotent by (strategy_id, execution_id): calling it
    again for a pair already on record returns the existing
    LLMAgentStrategyUsage unchanged rather than appending a duplicate or
    updating applied/selection_score -- a caller should only call
    record() once it knows the final selected/applied facts for that
    pair. There is no update() or remove(): every other call for a
    genuinely new pair appends a new record, preserving Commit #5's own
    selection_score as fixed provenance.
    """

    def __init__(
        self,
        strategy_service: LLMAgentStrategyService,
        plan_execution_service: LLMAgentPlanExecutionService,
        store: LLMAgentStrategyUsageStore = None,
    ):
        self._strategy_service = strategy_service
        self._plan_execution_service = plan_execution_service
        self.store = store if store is not None else InMemoryLLMAgentStrategyUsageStore()

    def record(
        self, strategy_id: str, execution_id: str, selection_score: float, applied: bool
    ) -> LLMAgentStrategyUsage:
        """Append one usage record linking strategy_id to execution_id.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded (propagated, not wrapped)
            InvalidSelectionScoreError, InvalidAppliedFlagError: If
                selection_score/applied themselves fail validation
        """
        # Existence checks only -- neither call mutates strategy_id or
        # execution_id, and (unlike Commit #3) execution_id's status is
        # never inspected: usage is a fact about the plan, not a verdict
        # about how it went.
        self._strategy_service.get(strategy_id)

        existing = self._find_existing(strategy_id, execution_id)
        if existing is not None:
            return existing

        self._plan_execution_service.get(execution_id)

        self._validate_selection_score(selection_score)
        self._validate_applied(applied)

        usage = LLMAgentStrategyUsage(
            strategy_id=strategy_id,
            execution_id=execution_id,
            selection_score=selection_score,
            applied=applied,
        )
        return self.store.save(usage)

    def get(self, usage_id: str) -> LLMAgentStrategyUsage:
        usage = self.store.get(usage_id)
        if usage is None:
            raise UnknownAgentStrategyUsageError(usage_id)
        return usage

    def list_for_strategy(self, strategy_id: str) -> list:
        """Every usage record for strategy_id, oldest first -- the
        complete history, never collapsed to a single latest use.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        self._strategy_service.get(strategy_id)
        return self.store.list_for_strategy(strategy_id)

    def list_for_execution(self, execution_id: str) -> list:
        """Every strategy usage record for execution_id, oldest first --
        every strategy that was selected and/or applied for that
        execution's plan.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded (propagated, not wrapped)
        """
        self._plan_execution_service.get(execution_id)
        return self.store.list_for_execution(execution_id)

    def _find_existing(self, strategy_id: str, execution_id: str):
        for usage in self.store.list_for_strategy(strategy_id):
            if usage.execution_id == execution_id:
                return usage
        return None

    @staticmethod
    def _validate_selection_score(selection_score):
        if isinstance(selection_score, bool) or not isinstance(selection_score, (int, float)):
            raise InvalidSelectionScoreError(f"selection_score {selection_score!r} must be a number")
        if not (MIN_SELECTION_SCORE <= selection_score <= MAX_SELECTION_SCORE):
            raise InvalidSelectionScoreError(
                f"selection_score {selection_score!r} must be between "
                f"{MIN_SELECTION_SCORE} and {MAX_SELECTION_SCORE}"
            )

    @staticmethod
    def _validate_applied(applied):
        if not isinstance(applied, bool):
            raise InvalidAppliedFlagError(f"applied {applied!r} must be a bool")
