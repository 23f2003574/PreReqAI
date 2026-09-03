import json
import re

from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.llm.tool_execution import FAILED, RUNNING, SUCCEEDED

from .in_memory_store import InMemoryLLMAgentStrategyOutcomeStore
from .models import LLMAgentStrategyEffectiveness, LLMAgentStrategyOutcome
from .store import LLMAgentStrategyOutcomeStore

# Same secret-detection convention kept locally by
# backend.agent_execution_memory, backend.llm.project_context,
# backend.agent_strategy_library, backend.agent_memory_feedback, and
# backend.llm.tool_execution -- kept local here too rather than
# refactoring any of those.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _contains_secret(value) -> bool:
    if isinstance(value, str):
        return _looks_secret(value)
    if isinstance(value, dict):
        return any(_contains_secret(key) or _contains_secret(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item) for item in value)
    return False


class UnknownAgentStrategyOutcomeError(KeyError):
    """Raised when get() is given an outcome_id that was never recorded."""


class InvalidEvidenceError(ValueError):
    """Raised when evidence is not JSON-serializable."""


class SecretEvidenceError(ValueError):
    """Raised when evidence appears to carry a secret, credential, or raw
    sensitive tool output."""


class IncompleteExecutionError(ValueError):
    """Raised when record() is given an execution_id whose plan execution
    has not yet reached a terminal status (i.e. is still RUNNING)."""


class NonMeaningfulOutcomeError(ValueError):
    """Raised when record() is given an execution_id whose terminal status
    is neither SUCCEEDED nor FAILED -- a REJECTED (nothing ever ran) or
    CANCELLED (stopped mid-way, by request) run is not evidence of how the
    strategy itself performed."""


class LLMAgentStrategyOutcomeService:
    """Records how a Commit #1 strategy actually performed when a real
    execution used it, and summarizes that history for one strategy.

    Not a second execution-analytics system: persistence is the same
    save/get/list_for_ split backend.agent_memory_feedback already uses
    (an InMemoryLLMAgentStrategyOutcomeStore by default, or the
    JSON-file-backed store built on the same backend.storage.AtomicJsonFile
    every other module here uses), and evidence is screened with the exact
    same secret-detection convention every other module here already keeps
    locally. record() never takes strategy_id or execution_id on faith: it
    reads Commit #1's own LLMAgentStrategyService.get(strategy_id) and the
    real LLMAgentPlanExecutionService.get(execution_id), each propagating
    that service's own "unknown" error unchanged rather than an
    outcome-specific wrapper. Neither call ever mutates what it reads.

    result is never taken on the caller's word either -- the same
    discipline backend.agent_execution_memory.LLMAgentMemoryService.
    record() already applies: only a genuinely terminal (not RUNNING) and
    meaningful (SUCCEEDED or FAILED, never REJECTED/CANCELLED) execution
    status is accepted, and result is always that verified status.

    record() is idempotent by (strategy_id, execution_id): calling it
    again for a pair already on record returns the existing
    LLMAgentStrategyOutcome unchanged rather than appending a duplicate --
    history is preserved and never overwritten, but the same real-world
    event is never double-counted in summarize()'s aggregates either.
    Every other call for a genuinely new pair appends a new record; there
    is no update() or remove().

    summarize() reads that same history through list_for_strategy() and
    aggregates it into an LLMAgentStrategyEffectiveness -- a fresh,
    recomputed count every call, never itself stored, and never fed back
    into the strategy's own status or ranking (no automatic lifecycle or
    ranking decision is made here yet).
    """

    def __init__(
        self,
        strategy_service: LLMAgentStrategyService,
        plan_execution_service: LLMAgentPlanExecutionService,
        store: LLMAgentStrategyOutcomeStore = None,
    ):
        self._strategy_service = strategy_service
        self._plan_execution_service = plan_execution_service
        self.store = store if store is not None else InMemoryLLMAgentStrategyOutcomeStore()

    def record(self, strategy_id: str, execution_id: str, evidence=None) -> LLMAgentStrategyOutcome:
        """Append one outcome for strategy_id, derived from execution_id's
        own verified terminal status.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded (propagated, not wrapped)
            IncompleteExecutionError: If that execution is still RUNNING
            NonMeaningfulOutcomeError: If its terminal status is neither
                SUCCEEDED nor FAILED
            InvalidEvidenceError, SecretEvidenceError: If evidence itself
                fails validation
        """
        # Existence checks only -- neither call mutates strategy_id or
        # execution_id.
        self._strategy_service.get(strategy_id)

        existing = self._find_existing(strategy_id, execution_id)
        if existing is not None:
            return existing

        execution = self._plan_execution_service.get(execution_id)

        if execution.status == RUNNING:
            raise IncompleteExecutionError(
                f"execution {execution_id!r} has not completed yet (status={execution.status})"
            )
        if execution.status not in (SUCCEEDED, FAILED):
            raise NonMeaningfulOutcomeError(
                f"execution {execution_id!r} ended as {execution.status}, "
                f"which carries no evidence of strategy performance"
            )

        evidence = {} if evidence is None else evidence
        self._validate_evidence(evidence)

        outcome = LLMAgentStrategyOutcome(
            strategy_id=strategy_id,
            execution_id=execution_id,
            result=execution.status,
            evidence=evidence,
        )
        return self.store.save(outcome)

    def get(self, outcome_id: str) -> LLMAgentStrategyOutcome:
        outcome = self.store.get(outcome_id)
        if outcome is None:
            raise UnknownAgentStrategyOutcomeError(outcome_id)
        return outcome

    def list_for_strategy(self, strategy_id: str) -> list:
        """Every outcome recorded for strategy_id, oldest first -- the
        complete history, never collapsed to a single latest result.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        self._strategy_service.get(strategy_id)
        return self.store.list_for_strategy(strategy_id)

    def summarize(self, strategy_id: str) -> LLMAgentStrategyEffectiveness:
        """Aggregate every outcome on record for strategy_id right now.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        outcomes = self.list_for_strategy(strategy_id)

        total = len(outcomes)
        succeeded = sum(1 for outcome in outcomes if outcome.result == SUCCEEDED)
        failed = sum(1 for outcome in outcomes if outcome.result == FAILED)
        success_rate = round(succeeded / total, 6) if total else 0.0
        last_outcome_at = max((outcome.created_at for outcome in outcomes), default=None)

        return LLMAgentStrategyEffectiveness(
            strategy_id=strategy_id,
            total_outcomes=total,
            succeeded_count=succeeded,
            failed_count=failed,
            success_rate=success_rate,
            last_outcome_at=last_outcome_at,
        )

    def _find_existing(self, strategy_id: str, execution_id: str):
        for outcome in self.store.list_for_strategy(strategy_id):
            if outcome.execution_id == execution_id:
                return outcome
        return None

    @staticmethod
    def _validate_evidence(evidence):
        try:
            json.dumps(evidence)
        except (TypeError, ValueError) as error:
            raise InvalidEvidenceError("evidence must be JSON-serializable") from error

        if _contains_secret(evidence):
            raise SecretEvidenceError(
                "evidence appears to contain a secret, credential, or raw sensitive "
                "tool output and cannot be stored"
            )
