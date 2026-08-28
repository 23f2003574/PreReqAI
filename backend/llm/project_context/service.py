import json
import re

from .in_memory_store import InMemoryLLMProjectContextStore
from .models import VALID_CONTEXT_TYPES, LLMProjectContext
from .store import LLMProjectContextStore

# Same secret-detection convention used by backend.transformation_audit,
# backend.api_recommendation_export, backend.llm.tool_execution,
# backend.llm.tool_results, and backend.llm.tool_audit.
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


class UnknownProjectContextError(KeyError):
    """Raised when looking up a context_id that has not been created."""


class InvalidContextTypeError(ValueError):
    """Raised when context_type is not one of VALID_CONTEXT_TYPES."""


class InvalidContentError(ValueError):
    """Raised when content is missing or is not JSON-serializable."""


class SecretContentError(ValueError):
    """Raised when content appears to carry a secret or credential."""


class LLMProjectContextService:
    """Creates, reads, and reuses durable context for one project/notebook/API scope.

    Persists through an LLMProjectContextStore (in-memory by default, or the
    JSON-file-backed store built on backend.storage.AtomicJsonFile) rather
    than a second storage framework -- the same split backend.session already
    uses between its research artifact store and manager. This is
    deliberately a different object from backend.llm.context.LLMContext:
    that one is assembled fresh per LLM call, this one is written once and
    read back across many notebook/API workflows sharing a scope_id.
    """

    def __init__(self, store: LLMProjectContextStore = None):
        self.store = store if store is not None else InMemoryLLMProjectContextStore()

    def create(
        self, scope_id: str, context_type: str, content, metadata: dict = None
    ) -> LLMProjectContext:
        self._validate_scope_id(scope_id)
        self._validate_context_type(context_type)
        self._validate_content(content)

        context = LLMProjectContext(
            scope_id=scope_id,
            context_type=context_type,
            content=content,
            metadata=dict(metadata) if metadata else {},
        )
        return self.store.save(context)

    def get(self, context_id: str) -> LLMProjectContext:
        context = self.store.get(context_id)
        if context is None:
            raise UnknownProjectContextError(context_id)
        return context

    def update(self, context_id: str, content) -> LLMProjectContext:
        self._validate_content(content)

        context = self.get(context_id)
        context.content = content
        return self.store.save(context)

    def delete(self, context_id: str) -> bool:
        return self.store.delete(context_id)

    def list(self, scope_id: str, context_type: str = None) -> list:
        self._validate_scope_id(scope_id)
        if context_type is not None:
            self._validate_context_type(context_type)
        return self.store.list_for_scope(scope_id, context_type)

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError(
                "scope_id is required and must identify a project/notebook/API"
            )

    @staticmethod
    def _validate_context_type(context_type):
        if context_type not in VALID_CONTEXT_TYPES:
            raise InvalidContextTypeError(
                f"context_type {context_type!r} is not one of {sorted(VALID_CONTEXT_TYPES)}"
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
