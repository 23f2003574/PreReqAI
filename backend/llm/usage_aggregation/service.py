from datetime import datetime

from ..usage import LLMUsageService

_EMPTY_TOTALS = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "count": 0}


class LLMUsageAggregationService:
    """Aggregates Commit #6's existing LLMUsageRecord data -- no new usage model.

    Reuses backend.llm.usage.LLMUsageService as the sole source of truth:
    every method here only reads through it (via its own scope_id
    convention -- None for everything, a request_id to narrow it) and never
    writes back, so a usage record is never mutated by being aggregated.
    """

    def __init__(self, usage_service: LLMUsageService):
        self._usage_service = usage_service

    def _records(self, scope) -> tuple:
        return self._usage_service.records(scope)

    @staticmethod
    def _totals_from(records) -> dict:
        if not records:
            return dict(_EMPTY_TOTALS)
        return {
            "input_tokens": sum(record.input_tokens for record in records),
            "output_tokens": sum(record.output_tokens for record in records),
            "total_tokens": sum(record.total_tokens for record in records),
            "count": len(records),
        }

    def totals(self, scope: str = None) -> dict:
        """Input/output/total token sums for scope, or everything if omitted."""
        return self._totals_from(self._records(scope))

    def _group_by(self, scope, key) -> dict:
        groups = {}
        for record in self._records(scope):
            groups.setdefault(key(record), []).append(record)
        return {group_key: self._totals_from(records) for group_key, records in groups.items()}

    def by_provider(self, scope: str = None) -> dict:
        """Token totals grouped by provider, preserving provider identity."""
        return self._group_by(scope, key=lambda record: record.provider)

    def by_model(self, scope: str = None) -> dict:
        """Token totals grouped by model, preserving model identity."""
        return self._group_by(scope, key=lambda record: record.model)

    def by_period(self, scope: str, start: datetime, end: datetime) -> dict:
        """Token totals for scope, narrowed to records recorded within [start, end]."""
        if start > end:
            raise ValueError("start must not be after end")

        matching = [
            record for record in self._records(scope) if start <= record.recorded_at <= end
        ]
        return self._totals_from(matching)

    def aggregate(self, scope: str = None) -> dict:
        """The full breakdown for scope: overall totals plus by-provider/by-model."""
        return {
            "totals": self.totals(scope),
            "by_provider": self.by_provider(scope),
            "by_model": self.by_model(scope),
        }
