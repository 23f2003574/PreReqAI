from datetime import datetime, timezone

from ..audit import LLMRequestAudit
from .models import LLMRequestLatency


class IncompleteRequestError(ValueError):
    """Raised when record() is given a request whose audit trail has not completed."""


class UnknownRequestLatencyError(KeyError):
    """Raised when looking up a request_id with no recorded latency."""


class LLMRequestLatencyService:
    """Measures duration for a request from its own Commit #5 audit snapshot.

    Reuses backend.llm.audit.LLMRequestAudit end to end: request_id,
    provider, model, status, and the created_at/completed_at pair a
    request's lifecycle already produced through
    LLMRequestOrchestrationService's own start()/complete() calls. No
    second request-tracking system, no timer of its own -- duration is
    exactly completed_at - created_at from that existing record.
    """

    def __init__(self):
        self._latencies = {}

    def record(self, request: LLMRequestAudit) -> LLMRequestLatency:
        if request.completed_at is None:
            raise IncompleteRequestError(
                f"request {request.request_id!r} has not completed yet -- its audit "
                "trail carries no completed_at"
            )

        duration = (request.completed_at - request.created_at).total_seconds()

        latency = LLMRequestLatency(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            duration=duration,
            status=request.status,
            recorded_at=datetime.now(timezone.utc),
        )
        latency.validate()

        self._latencies[request.request_id] = latency
        return latency

    def get(self, request_id: str) -> LLMRequestLatency:
        try:
            return self._latencies[request_id]
        except KeyError:
            raise UnknownRequestLatencyError(request_id)

    def aggregate(self, provider: str, model: str) -> dict:
        """Deterministic latency stats for one provider/model pair.

        A pair with no recorded requests yet gets count=0 and
        average_duration=None -- never a fabricated zero average.
        """
        matches = [
            latency
            for latency in self._latencies.values()
            if latency.provider == provider and latency.model == model
        ]

        status_counts = {}
        for latency in matches:
            status_counts[latency.status] = status_counts.get(latency.status, 0) + 1

        return {
            "provider": provider,
            "model": model,
            "count": len(matches),
            "average_duration": (
                round(sum(latency.duration for latency in matches) / len(matches), 6)
                if matches
                else None
            ),
            "status_counts": status_counts,
        }
