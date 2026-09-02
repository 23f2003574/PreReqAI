import json
import re

from backend.llm.tool_execution import FAILED, RUNNING, SUCCEEDED

from .in_memory_store import InMemoryLLMAgentMemoryStore
from .models import VALID_MEMORY_TYPES, LLMAgentMemory
from .store import LLMAgentMemoryStore

# Same secret-detection convention already kept locally by
# backend.llm.project_context, backend.llm.tool_execution,
# backend.llm.tool_results, backend.llm.tool_audit, and
# backend.agent_execution_reporting -- kept local here too rather than
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


class UnknownAgentMemoryError(KeyError):
    """Raised when get()/remove() is given a memory_id that was never recorded."""


class InvalidMemoryTypeError(ValueError):
    """Raised when memory_type is not one of VALID_MEMORY_TYPES."""


class InvalidContentError(ValueError):
    """Raised when content is missing or is not JSON-serializable."""


class SecretContentError(ValueError):
    """Raised when content appears to carry a secret or credential."""


class IncompleteExecutionError(ValueError):
    """Raised when record() is given an execution_id whose plan execution
    has not yet reached a terminal status (i.e. is still RUNNING)."""


class NonMeaningfulOutcomeError(ValueError):
    """Raised when record() is given an execution_id whose terminal status
    is neither SUCCEEDED nor FAILED. A REJECTED (nothing ever ran) or
    CANCELLED (stopped mid-way, by request) run carries no proven
    execution knowledge worth reusing."""


class LLMAgentMemoryService:
    """Records and reuses proven outcomes distilled from completed agent executions.

    Not a second memory or context framework: persistence is the same
    save/get/delete/list_for_scope split backend.llm.project_context
    already uses (an InMemoryLLMAgentMemoryStore by default, or the
    JSON-file-backed store built on the same backend.storage.AtomicJsonFile
    project_context itself uses), and content is screened with the exact
    same secret-detection convention every other module here already
    keeps locally. What this service adds that project_context has no
    notion of is entirely about the *originating execution*: record()
    never takes a caller's word for whether an execution finished, or how
    it went -- it reads Commit #12's own LLMAgentPlanExecutionService
    record for execution_id and only ever accepts one that is genuinely
    terminal (status is not RUNNING) and meaningful (SUCCEEDED or FAILED,
    never REJECTED/CANCELLED, which reflect nothing the execution actually
    did). outcome is always that verified status, never something the
    caller supplies -- the same discipline
    backend.agent_execution_context.record_step() applies when it refuses
    to trust a caller-supplied step result until it matches Commit #3's
    own record.

    record() only ever reads plan_execution_service.get(execution_id); it
    never cancels, re-runs, or otherwise mutates that execution, so
    recording a memory can never alter execution state.
    """

    def __init__(self, plan_execution_service, store: LLMAgentMemoryStore = None):
        self._plan_execution_service = plan_execution_service
        self.store = store if store is not None else InMemoryLLMAgentMemoryStore()

    def record(self, execution_id: str, memory: dict) -> LLMAgentMemory:
        """Distill one completed execution's outcome into a durable memory.

        `memory` carries only what the caller actually knows: scope_id,
        memory_type, and content. execution_id and outcome are never
        taken from it -- outcome is always the originating execution's own
        verified terminal status.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded by Commit #12 (propagated, not wrapped)
            IncompleteExecutionError: If that execution is still RUNNING
            NonMeaningfulOutcomeError: If its terminal status is neither
                SUCCEEDED nor FAILED
            InvalidMemoryTypeError, InvalidContentError, SecretContentError:
                Same validation backend.llm.project_context.create() applies
        """
        execution = self._plan_execution_service.get(execution_id)

        if execution.status == RUNNING:
            raise IncompleteExecutionError(
                f"execution {execution_id!r} has not completed yet (status={execution.status})"
            )
        if execution.status not in (SUCCEEDED, FAILED):
            raise NonMeaningfulOutcomeError(
                f"execution {execution_id!r} ended as {execution.status}, "
                f"which carries no reusable execution outcome"
            )

        scope_id = memory.get("scope_id")
        memory_type = memory.get("memory_type")
        content = memory.get("content")

        self._validate_scope_id(scope_id)
        self._validate_memory_type(memory_type)
        self._validate_content(content)

        record = LLMAgentMemory(
            scope_id=scope_id,
            execution_id=execution_id,
            memory_type=memory_type,
            content=content,
            outcome=execution.status,
        )
        return self.store.save(record)

    def get(self, memory_id: str) -> LLMAgentMemory:
        record = self.store.get(memory_id)
        if record is None:
            raise UnknownAgentMemoryError(memory_id)
        return record

    def list(self, scope_id: str, memory_type: str = None) -> list:
        self._validate_scope_id(scope_id)
        if memory_type is not None:
            self._validate_memory_type(memory_type)
        return self.store.list_for_scope(scope_id, memory_type)

    def remove(self, memory_id: str) -> bool:
        return self.store.delete(memory_id)

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required and must identify a project/notebook/API")

    @staticmethod
    def _validate_memory_type(memory_type):
        if memory_type not in VALID_MEMORY_TYPES:
            raise InvalidMemoryTypeError(
                f"memory_type {memory_type!r} is not one of {sorted(VALID_MEMORY_TYPES)}"
            )

    @staticmethod
    def _validate_content(content):
        if content is None or content == "" or content == {} or content == []:
            raise InvalidContentError("content is required")

        try:
            json.dumps(content)
        except (TypeError, ValueError) as error:
            raise InvalidContentError("content must be JSON-serializable") from error

        if _contains_secret(content):
            raise SecretContentError(
                "content appears to contain a secret or credential and cannot be stored"
            )
