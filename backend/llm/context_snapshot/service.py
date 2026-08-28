import re
from copy import deepcopy

from ..context import estimate_text_tokens
from ..context_injection import CONTEXT_ROLE
from ..models import LLMRequest
from .models import LLMContextSnapshot

# Same secret-detection convention used by backend.transformation_audit,
# backend.api_recommendation_export, backend.llm.tool_execution,
# backend.llm.tool_results, backend.llm.tool_audit, backend.llm.
# project_context, and backend.llm.context_provenance. Content reaching
# this service should already be clean -- Commit #1 refuses secret content
# outright, and Commit #6 refuses a secret excerpt -- but, as
# backend.llm.tool_results' own comment puts it, redacting again is
# idempotent and keeps this service safe on its own.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

_REDACTED = "[REDACTED]"


def _redact(value) -> str:
    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return _REDACTED
    return text


class UnknownSnapshotError(KeyError):
    """Raised when get() names a snapshot_id that was never created."""


class LLMContextSnapshotService:
    """Records an immutable snapshot of the context actually sent with one LLM request.

    Reuses Commit #7's CONTEXT_ROLE to pick the injected context messages
    back out of the LLMRequest it produced -- not Commit #3's raw
    candidates -- and backend.llm.context's estimate_text_tokens for the
    recorded token_count, the same estimator every earlier commit already
    uses. Holds its own append-style record in memory, the same shape
    backend.llm.audit, backend.llm.tool_audit, and Commit #6's
    LLMContextProvenanceService already use for a trail, rather than a
    second persistence framework: create() only reads the LLMRequest it is
    given, and no snapshot is ever edited or removed once written.
    """

    def __init__(self):
        self._snapshots: dict[str, LLMContextSnapshot] = {}
        self._snapshot_ids_by_request: dict[str, list] = {}

    def create(self, request_id: str, context: LLMRequest) -> LLMContextSnapshot:
        if not request_id or not isinstance(request_id, str):
            raise ValueError("request_id is required")

        if not isinstance(context, LLMRequest):
            raise ValueError(
                "context must be the LLMRequest produced by "
                "LLMContextInjectionService.inject()"
            )

        context_items = tuple(
            self._normalize_item(message)
            for message in context.messages
            if message.get("role") == CONTEXT_ROLE
        )

        scope_ids = {item["scope_id"] for item in context_items if item.get("scope_id")}
        scope_id = next(iter(scope_ids)) if len(scope_ids) == 1 else None

        token_count = sum(estimate_text_tokens(item["content"]) for item in context_items)

        snapshot = LLMContextSnapshot(
            request_id=request_id,
            scope_id=scope_id,
            context_items=context_items,
            token_count=token_count,
        )

        self._snapshots[snapshot.snapshot_id] = snapshot
        self._snapshot_ids_by_request.setdefault(request_id, []).append(snapshot.snapshot_id)
        return snapshot

    def get(self, snapshot_id: str) -> LLMContextSnapshot:
        try:
            snapshot = self._snapshots[snapshot_id]
        except KeyError:
            raise UnknownSnapshotError(snapshot_id)
        return self._copy(snapshot)

    def for_request(self, request_id: str) -> list:
        """Every snapshot recorded for request_id, in the order created."""
        return [
            self._copy(self._snapshots[snapshot_id])
            for snapshot_id in self._snapshot_ids_by_request.get(request_id, [])
        ]

    @staticmethod
    def _copy(snapshot: LLMContextSnapshot) -> LLMContextSnapshot:
        """A defensive copy: frozen fields cannot be reassigned, but the
        context_items tuple holds plain dicts a caller could otherwise
        mutate in place."""
        return LLMContextSnapshot(
            request_id=snapshot.request_id,
            scope_id=snapshot.scope_id,
            context_items=tuple(deepcopy(item) for item in snapshot.context_items),
            token_count=snapshot.token_count,
            snapshot_id=snapshot.snapshot_id,
            created_at=snapshot.created_at,
        )

    def _normalize_item(self, message: dict) -> dict:
        metadata = message.get("metadata") or {}
        provenance = metadata.get("provenance")

        return {
            "context_id": metadata.get("context_id"),
            "scope_id": metadata.get("scope_id"),
            "context_type": metadata.get("context_type"),
            "content": _redact(message.get("content")),
            "provenance": self._normalize_provenance(provenance) if provenance else None,
        }

    @staticmethod
    def _normalize_provenance(provenance: dict) -> dict:
        return {
            "source_type": provenance.get("source_type"),
            "source_id": _redact(provenance.get("source_id")),
            "source_version": provenance.get("source_version"),
            "excerpt": _redact(provenance.get("excerpt")),
        }
