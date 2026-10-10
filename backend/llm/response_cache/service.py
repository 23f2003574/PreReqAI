import hashlib
import json
from datetime import datetime, timedelta, timezone

from ..models import LLMRequest, LLMResponse
from .models import LLMCacheEntry

# Finish reasons that indicate an unsuccessful completion; never cached.
FAILURE_FINISH_REASONS = {"error", "content_filter", "timeout", "cancelled"}


class LLMResponseCacheService:
    """Caches deterministic LLMResponses (Commit #1) keyed on model + request content.

    Built entirely on backend.llm.LLMRequest/LLMResponse -- any request built
    from Commit #4's LLMContextService.build() output, or resolved via
    Commit #3's routing, works here unchanged.
    """

    def __init__(self):
        self._entries = {}

    @staticmethod
    def _request_hash(request: LLMRequest) -> str:
        payload = {
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def compute_key(self, request: LLMRequest) -> str:
        return f"{request.model}:{self._request_hash(request)}"

    @staticmethod
    def _is_successful(response: LLMResponse) -> bool:
        return bool(response.content) and response.finish_reason not in FAILURE_FINISH_REASONS

    def get(self, request: LLMRequest):
        key = self.compute_key(request)
        entry = self._entries.get(key)
        if entry is None:
            return None

        if entry.expires_at is not None and entry.expires_at <= datetime.now(timezone.utc):
            del self._entries[key]
            return None

        return entry.response

    def set(self, request: LLMRequest, response: LLMResponse, ttl=None, cacheable=True):
        if not cacheable:
            return None

        if not self._is_successful(response):
            return None

        now = datetime.now(timezone.utc)
        expires_at = None if ttl is None else now + timedelta(seconds=ttl)

        entry = LLMCacheEntry(
            cache_key=self.compute_key(request),
            request_hash=self._request_hash(request),
            response=response,
            model=request.model,
            expires_at=expires_at,
            created_at=now,
        )
        self._entries[entry.cache_key] = entry
        return entry

    def invalidate(self, request: LLMRequest) -> bool:
        return self._entries.pop(self.compute_key(request), None) is not None

    def clear(self, scope_id: str = None) -> int:
        """Remove cached entries for one model (`scope_id`), or all if omitted."""
        if scope_id is None:
            count = len(self._entries)
            self._entries.clear()
            return count

        keys_to_remove = [
            key for key, entry in self._entries.items() if entry.model == scope_id
        ]
        for key in keys_to_remove:
            del self._entries[key]
        return len(keys_to_remove)
