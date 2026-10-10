from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_alert_route_error import (
    ExecutionObservabilityAlertRouteError,
)

from .execution_observability_event import (
    SEVERITIES,
)

SEVERITY_ANY = "ANY"

ROUTE_SEVERITIES = SEVERITIES + (SEVERITY_ANY,)


@dataclass(frozen=True)
class ExecutionObservabilityAlertRoute:
    """
    Immutable definition of where alerts of a given severity should
    be routed for notification.

    The route is a value object only. It performs no matching of its
    own; registering routes and resolving them against an alert's
    severity is the responsibility of an execution alert routing
    service, which produces a new record for every transition (such
    as disabling a route) rather than mutating an existing one.

    Attributes:
        route_id: The route's unique identifier
        severity: The severity this route applies to, one of
            ROUTE_SEVERITIES; SEVERITY_ANY matches every severity but
            is the least specific match
        destination: Where a matching alert should be delivered, e.g.
            "pagerduty:oncall" or "slack:#alerts"
        enabled: Whether the route is currently active
        created_at: When the route was registered
    """

    severity: str

    destination: str

    route_id: str = field(default_factory=lambda: str(uuid4()))

    enabled: bool = True

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.route_id, "route ID")
        self._require_text(self.destination, "destination")

        if self.severity not in ROUTE_SEVERITIES:
            raise ExecutionObservabilityAlertRouteError(
                f"Cannot build an execution observability alert route with an unknown severity: {self.severity!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionObservabilityAlertRouteError(
                "Cannot build an execution observability alert route with a non-boolean enabled."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionObservabilityAlertRouteError(
                "Cannot build an execution observability alert route with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertRouteError(
                f"Cannot build an execution observability alert route with an empty or blank {field_name}."
            )
