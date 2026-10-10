import json
import re

from backend.agent_execution_memory import LLMAgentMemoryService

from .in_memory_store import InMemoryLLMAgentStrategyStore
from .models import ACTIVE, ARCHIVED, STATUSES, LLMAgentStrategy
from .store import LLMAgentStrategyStore

# Same secret-detection convention kept locally by
# backend.llm.project_context, backend.agent_execution_memory,
# backend.llm.tool_execution, backend.llm.tool_results, and
# backend.llm.tool_audit -- kept local here too rather than refactoring
# any of those.
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


class UnknownAgentStrategyError(KeyError):
    """Raised when get()/update()/archive() is given a strategy_id that was never created."""


class InvalidStrategyDataError(ValueError):
    """Raised when strategy_data is missing or is not JSON-serializable."""


class SecretStrategyDataError(ValueError):
    """Raised when strategy_data appears to carry a secret or credential."""


class InvalidStrategyStatusError(ValueError):
    """Raised when a status argument is not one of STATUSES."""


class EmptyProvenanceError(ValueError):
    """Raised when create() is given no source memories at all -- a
    strategy must always be justified by at least one Commit #1
    execution memory, never asserted from nothing."""


class CrossScopeProvenanceError(ValueError):
    """Raised when a source memory named in source_memory_ids belongs to a
    different scope than the strategy being created -- provenance can
    never cross a scope boundary, the same isolation
    LLMAgentMemoryService.list() itself already enforces."""


class ArchivedStrategyError(ValueError):
    """Raised when update() is given a strategy_id that is already ARCHIVED.

    An archived strategy is retired, deliberately-preserved history --
    the same reasoning backend.agent_memory_promotion refuses to silently
    re-trust a DEPRECATED memory. Reviving one requires a fresh create()
    call, not a mutation of the archived record.
    """


class LLMAgentStrategyService:
    """Creates, reads, and retires named strategies distilled from proven
    Commit #1 execution memories -- a scope-level, planning-facing layer
    kept entirely separate from memory storage itself.

    Not a second memory subsystem: persistence is the same save/get/
    list_for_scope split backend.llm.project_context and
    backend.agent_execution_memory already use (an
    InMemoryLLMAgentStrategyStore by default, or the JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile they use), and
    strategy_data is screened with the exact same secret-detection
    convention every other module here already keeps locally. What this
    service adds that neither of those has any notion of is provenance:
    create() never accepts source_memory_ids on faith -- each id is
    resolved through the real LLMAgentMemoryService.get() (propagating
    UnknownAgentMemoryError if one does not exist) and must belong to the
    same scope_id as the strategy itself, so a strategy's justification
    always traces back to real, scope-matched execution memories (and,
    transitively, through each memory's own execution_id, to the
    execution that produced it).

    There is no automatic strategy generation here: create() only ever
    records what a caller explicitly names, never derives a strategy from
    memory on its own.
    """

    def __init__(self, memory_service: LLMAgentMemoryService, store: LLMAgentStrategyStore = None):
        self._memory_service = memory_service
        self.store = store if store is not None else InMemoryLLMAgentStrategyStore()

    def create(
        self,
        scope_id: str,
        name: str,
        description: str,
        strategy_data,
        source_memory_ids: list,
    ) -> LLMAgentStrategy:
        """Record a new, ACTIVE strategy for scope_id, justified by the
        given source memories.

        Raises:
            ValueError: If scope_id, name, or description is missing
            InvalidStrategyDataError, SecretStrategyDataError: Same
                validation backend.llm.project_context.create() applies
                to strategy_data
            EmptyProvenanceError: If source_memory_ids is empty
            UnknownAgentMemoryError: If any id in source_memory_ids was
                never recorded by Commit #1 (propagated, not wrapped)
            CrossScopeProvenanceError: If a source memory belongs to a
                different scope than scope_id
        """
        self._validate_scope_id(scope_id)
        self._validate_name(name)
        self._validate_description(description)
        self._validate_strategy_data(strategy_data)
        resolved_ids = self._validate_provenance(scope_id, source_memory_ids)

        strategy = LLMAgentStrategy(
            scope_id=scope_id,
            name=name,
            description=description,
            strategy_data=strategy_data,
            source_memory_ids=resolved_ids,
            status=ACTIVE,
        )
        return self.store.save(strategy)

    def get(self, strategy_id: str) -> LLMAgentStrategy:
        strategy = self.store.get(strategy_id)
        if strategy is None:
            raise UnknownAgentStrategyError(strategy_id)
        return strategy

    def list(self, scope_id: str, status: str = None) -> list:
        self._validate_scope_id(scope_id)
        if status is not None:
            self._validate_status(status)
        return self.store.list_for_scope(scope_id, status)

    def update(
        self,
        strategy_id: str,
        name: str = None,
        description: str = None,
        strategy_data=None,
    ) -> LLMAgentStrategy:
        """Update one or more of name/description/strategy_data on an
        existing, still-ACTIVE strategy. Fields left as None are
        unchanged. Provenance (source_memory_ids) is never mutated here --
        a strategy's justification is fixed at create() time.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created
            ArchivedStrategyError: If strategy_id is already ARCHIVED
            InvalidStrategyDataError, SecretStrategyDataError: If
                strategy_data is given and fails validation
        """
        strategy = self.get(strategy_id)
        if strategy.status == ARCHIVED:
            raise ArchivedStrategyError(
                f"strategy {strategy_id!r} is archived and cannot be updated"
            )

        if name is not None:
            self._validate_name(name)
            strategy.name = name
        if description is not None:
            self._validate_description(description)
            strategy.description = description
        if strategy_data is not None:
            self._validate_strategy_data(strategy_data)
            strategy.strategy_data = strategy_data

        return self.store.save(strategy)

    def archive(self, strategy_id: str) -> LLMAgentStrategy:
        """Retire strategy_id by marking it ARCHIVED, never by deleting it --
        an archived strategy, and its full provenance, stays exactly as
        reachable through get()/list() as any other. Idempotent: archiving
        an already-ARCHIVED strategy simply returns it unchanged.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created
        """
        strategy = self.get(strategy_id)
        if strategy.status == ARCHIVED:
            return strategy

        strategy.status = ARCHIVED
        return self.store.save(strategy)

    def provenance(self, strategy_id: str) -> list:
        """The full LLMAgentMemory records that justify strategy_id, in
        the order they were named at create() time -- each still carrying
        its own execution_id and verified outcome, so a strategy's
        justification is always traceable back to real executions.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created
        """
        strategy = self.get(strategy_id)
        return [self._memory_service.get(memory_id) for memory_id in strategy.source_memory_ids]

    def _validate_provenance(self, scope_id: str, source_memory_ids: list) -> list:
        if not source_memory_ids or not isinstance(source_memory_ids, list):
            raise EmptyProvenanceError(
                "source_memory_ids is required and must name at least one execution memory"
            )

        resolved_ids = []
        for memory_id in source_memory_ids:
            memory = self._memory_service.get(memory_id)
            if memory.scope_id != scope_id:
                raise CrossScopeProvenanceError(
                    f"memory {memory_id!r} belongs to scope {memory.scope_id!r}, "
                    f"not {scope_id!r}"
                )
            resolved_ids.append(memory_id)
        return resolved_ids

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required and must identify a project/notebook/API")

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str):
            raise ValueError("name is required")

    @staticmethod
    def _validate_description(description):
        if not description or not isinstance(description, str):
            raise ValueError("description is required")

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidStrategyStatusError(f"status {status!r} is not one of {sorted(STATUSES)}")

    @staticmethod
    def _validate_strategy_data(strategy_data):
        if strategy_data is None or strategy_data == "" or strategy_data == {} or strategy_data == []:
            raise InvalidStrategyDataError("strategy_data is required")

        try:
            json.dumps(strategy_data)
        except (TypeError, ValueError) as error:
            raise InvalidStrategyDataError("strategy_data must be JSON-serializable") from error

        if _contains_secret(strategy_data):
            raise SecretStrategyDataError(
                "strategy_data appears to contain a secret or credential and cannot be stored"
            )
