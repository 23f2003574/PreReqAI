import dataclasses
from datetime import datetime, timezone

from ..cost import LLMCostService, UnknownPricingError
from ..usage import LLMUsageService, UnknownRequestError
from .models import LLMRequestAudit


class UnknownAuditRequestError(KeyError):
    """Raised when looking up a request_id with no audit trail started."""


class DuplicateAuditRequestError(ValueError):
    """Raised when start() is called twice for the same request_id."""


class LLMRequestAuditService:
    """Append-only audit trail for an LLM request's lifecycle across fallbacks.

    Every lifecycle event appends a new immutable LLMRequestAudit snapshot to
    that request's trail rather than mutating the previous one. Reuses
    Commit #6's LLMUsageService and Commit #7's LLMCostService to compute
    total_tokens/total_cost -- this service never invents its own
    token/cost accounting, it only reflects what those services already
    recorded (typically via Commit #10's retry / Commit #11's fallback flows
    calling a Commit #1 provider and recording usage as normal).
    """

    def __init__(self, usage_service: LLMUsageService, cost_service: LLMCostService = None):
        self._usage_service = usage_service
        self._cost_service = cost_service
        self._trails = {}

    def _totals(self, request_id: str):
        total_tokens = self._usage_service.total(request_id)

        total_cost = 0.0
        if self._cost_service is not None:
            try:
                total_cost = self._cost_service.estimate(request_id).total_cost
            except (UnknownRequestError, UnknownPricingError):
                total_cost = 0.0

        return total_tokens, total_cost

    def _get_trail(self, request_id: str) -> list:
        try:
            return self._trails[request_id]
        except KeyError:
            raise UnknownAuditRequestError(request_id)

    def start(self, request, request_id: str, provider: str) -> LLMRequestAudit:
        if request_id in self._trails:
            raise DuplicateAuditRequestError(
                f"an audit trail already exists for request_id {request_id!r}"
            )

        total_tokens, total_cost = self._totals(request_id)

        audit = LLMRequestAudit(
            audit_id=f"audit-{request_id}-1",
            request_id=request_id,
            provider=provider,
            model=request.model,
            status="started",
            attempts=1,
            total_tokens=total_tokens,
            total_cost=total_cost,
            created_at=datetime.now(timezone.utc),
            completed_at=None,
        )
        self._trails[request_id] = [audit]
        return audit

    def record_attempt(self, request_id: str, provider: str, model: str) -> LLMRequestAudit:
        trail = self._get_trail(request_id)
        previous = trail[-1]
        total_tokens, total_cost = self._totals(request_id)

        audit = dataclasses.replace(
            previous,
            audit_id=f"audit-{request_id}-{len(trail) + 1}",
            provider=provider,
            model=model,
            attempts=previous.attempts + 1,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )
        trail.append(audit)
        return audit

    def complete(self, request_id: str, status: str) -> LLMRequestAudit:
        if not status or not isinstance(status, str):
            raise ValueError("status is required")

        trail = self._get_trail(request_id)
        previous = trail[-1]
        total_tokens, total_cost = self._totals(request_id)

        audit = dataclasses.replace(
            previous,
            audit_id=f"audit-{request_id}-{len(trail) + 1}",
            status=status,
            total_tokens=total_tokens,
            total_cost=total_cost,
            completed_at=datetime.now(timezone.utc),
        )
        trail.append(audit)
        return audit

    def get(self, request_id: str) -> LLMRequestAudit:
        """The current (most recent) audit snapshot -- one logical record per request."""
        return self._get_trail(request_id)[-1]

    def history(self, scope_id: str) -> list:
        """The full append-only trail of snapshots for one request_id."""
        return list(self._get_trail(scope_id))
