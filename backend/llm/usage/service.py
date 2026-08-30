from datetime import datetime, timezone

from ..models import LLMResponse
from .models import LLMUsageRecord

_INPUT_ALIASES = ("input_tokens", "prompt_tokens", "promptTokens", "prompt_token_count")
_OUTPUT_ALIASES = (
    "output_tokens",
    "completion_tokens",
    "completionTokens",
    "candidates_token_count",
)


class InvalidUsageError(ValueError):
    """Raised when a response's usage payload is missing or has bad counts."""


class UnknownRequestError(KeyError):
    """Raised when looking up usage for a request_id with no recorded usage."""


class LLMUsageService:
    """Normalizes provider usage payloads into one schema and stores them.

    record() takes the LLMResponse produced by a provider adapter (Commit #1)
    and the request_id/provider it was resolved for (Commit #3's routing),
    regardless of which token-count key names the raw response.usage used.
    """

    def __init__(self):
        self._records = []
        self._by_request = {}
        self._counter = 0

    @staticmethod
    def _extract(usage: dict, aliases):
        for key in aliases:
            if key in usage and usage[key] is not None:
                return usage[key]
        return None

    def record(self, response: LLMResponse, request_id: str, provider: str) -> LLMUsageRecord:
        if not request_id or not isinstance(request_id, str):
            raise InvalidUsageError("request_id is required")

        if not provider or not isinstance(provider, str):
            raise InvalidUsageError("provider is required")

        usage = response.usage or {}
        input_tokens = self._extract(usage, _INPUT_ALIASES)
        output_tokens = self._extract(usage, _OUTPUT_ALIASES)

        if input_tokens is None or output_tokens is None:
            raise InvalidUsageError(
                "response.usage is missing input/output token counts"
            )

        if (
            isinstance(input_tokens, bool)
            or isinstance(output_tokens, bool)
            or not isinstance(input_tokens, int)
            or not isinstance(output_tokens, int)
        ):
            raise InvalidUsageError("token counts must be integers")

        if input_tokens < 0 or output_tokens < 0:
            raise InvalidUsageError("token counts must not be negative")

        self._counter += 1
        record = LLMUsageRecord(
            usage_id=f"usage-{self._counter}",
            request_id=request_id,
            provider=provider,
            model=response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            recorded_at=datetime.now(timezone.utc),
        )

        self._records.append(record)
        self._by_request.setdefault(request_id, []).append(record)
        return record

    def get(self, request_id: str) -> tuple:
        try:
            records = self._by_request[request_id]
        except KeyError:
            raise UnknownRequestError(request_id)
        return tuple(records)

    def records(self, scope_id: str = None) -> tuple:
        """Every normalized record for scope_id, or all of them if omitted.

        Unlike get(), an unrecognized scope_id yields an empty tuple rather
        than raising -- a scope with nothing recorded is a valid, empty
        result, not an error.
        """
        return tuple(self._scoped_records(scope_id))

    def purge_before(self, cutoff, scope_id: str = None) -> int:
        """Remove records recorded before cutoff, narrowed to scope_id if given.

        Returns how many records were removed. Deterministic and explicit --
        called only when a caller names an exact cutoff, never on a timer.
        """
        removed = 0
        for request_id in list(self._by_request):
            if scope_id is not None and request_id != scope_id:
                continue
            kept = [record for record in self._by_request[request_id] if record.recorded_at >= cutoff]
            removed += len(self._by_request[request_id]) - len(kept)
            if kept:
                self._by_request[request_id] = kept
            else:
                del self._by_request[request_id]

        if scope_id is None:
            self._records = [record for record in self._records if record.recorded_at >= cutoff]
        else:
            self._records = [
                record
                for record in self._records
                if record.request_id != scope_id or record.recorded_at >= cutoff
            ]

        return removed

    def _scoped_records(self, scope_id) -> list:
        if scope_id is None:
            return list(self._records)
        return list(self._by_request.get(scope_id, []))

    def total(self, scope_id: str = None) -> int:
        """Sum of total_tokens for a request_id, or across everything if omitted."""
        return sum(record.total_tokens for record in self._scoped_records(scope_id))

    def by_model(self, scope_id: str = None) -> dict:
        """Token totals grouped by model, for a request_id or across everything."""
        totals = {}
        for record in self._scoped_records(scope_id):
            totals[record.model] = totals.get(record.model, 0) + record.total_tokens
        return totals
