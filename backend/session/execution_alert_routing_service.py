from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_observability_alert_route import (
    ExecutionObservabilityAlertRoute,
    SEVERITY_ANY,
)

from .execution_observability_alert_route_error import (
    ExecutionObservabilityAlertRouteError,
)


class ExecutionAlertRoutingService:
    """
    Routes active alerts to the appropriate notification destination
    based on severity.

    Composes with an existing alert service (anything exposing
    `get(alert_id)` -> object with `.severity`, matching
    ExecutionAlertService), used to read an alert's severity.
    Performs no alert triggering of its own, and never mutates the
    composed service.

    Behavior:
    - register() stores a route, keyed by route_id; registering
      under an already-used route_id replaces the prior route
    - resolve() reports the winning route for an alert: among
      enabled routes matching the alert's severity, an exact-severity
      match beats a SEVERITY_ANY match (highest specificity wins);
      ties within the same specificity are broken by the
      most-recently registered route; if nothing matches, the alert
      remains unrouted (None)
    - routes() reports every enabled route matching a severity,
      ordered from highest to lowest precedence (the order resolve()
      would pick from)
    - disable() is idempotent: disabling an already-disabled route
      simply returns it unchanged; disabled routes are ignored by
      resolve() and routes()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, alert_service):
        self._alert_service = alert_service
        self._routes_by_id = {}
        self._lock = RLock()

    def register(self, route: ExecutionObservabilityAlertRoute) -> ExecutionObservabilityAlertRoute:
        """
        Register (or replace) an alert route.

        Raises:
            ExecutionObservabilityAlertRouteError: If route is not an
                ExecutionObservabilityAlertRoute
        """

        if not isinstance(route, ExecutionObservabilityAlertRoute):
            raise ExecutionObservabilityAlertRouteError(
                "Cannot register an object that is not an ExecutionObservabilityAlertRoute."
            )

        with self._lock:
            self._routes_by_id[route.route_id] = route

            return route

    def resolve(self, alert_id: str):
        """
        The winning route for alert_id, or None if it remains
        unrouted.

        Raises:
            ExecutionObservabilityAlertRouteError: If alert_id is
                None or blank, or it is unknown to the alert service
        """

        self._validate_text(alert_id, "alert ID")

        alert = self._resolve_alert(alert_id)

        matches = self._matching_routes(alert.severity)

        return matches[0] if matches else None

    def routes(self, severity: str) -> tuple:
        """
        Every enabled route matching severity, from highest to
        lowest precedence.

        Raises:
            ExecutionObservabilityAlertRouteError: If severity is
                None or blank
        """

        self._validate_text(severity, "severity")

        return self._matching_routes(severity)

    def disable(self, route_id: str) -> ExecutionObservabilityAlertRoute:
        """
        Disable a registered route. Idempotent: disabling an
        already-disabled route simply returns it unchanged.

        Raises:
            ExecutionObservabilityAlertRouteError: If route_id is
                None or blank, or no route is registered under it
        """

        self._validate_text(route_id, "route ID")

        with self._lock:
            route = self._resolve_route(route_id)

            if not route.enabled:
                return route

            disabled = replace(route, enabled=False)
            self._routes_by_id[route_id] = disabled

            return disabled

    def _matching_routes(self, severity: str) -> tuple:
        with self._lock:
            candidates = list(self._routes_by_id.values())

        matching = [
            route
            for route in candidates
            if route.enabled and (route.severity == severity or route.severity == SEVERITY_ANY)
        ]

        return tuple(
            sorted(
                matching,
                key=lambda route: (self._specificity(route, severity), route.created_at),
                reverse=True,
            )
        )

    @staticmethod
    def _specificity(route: ExecutionObservabilityAlertRoute, severity: str) -> int:
        return 1 if route.severity == severity else 0

    def _resolve_alert(self, alert_id: str):
        try:
            return self._alert_service.get(alert_id)
        except Exception as error:
            raise ExecutionObservabilityAlertRouteError(
                f"Cannot resolve alert ID {alert_id!r}: it is unknown."
            ) from error

    def _resolve_route(self, route_id: str) -> ExecutionObservabilityAlertRoute:
        route = self._routes_by_id.get(route_id)

        if route is None:
            raise ExecutionObservabilityAlertRouteError(
                f"No route is registered under route ID {route_id!r}."
            )

        return route

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertRouteError(f"Cannot use an empty or blank {field_name}.")
