from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_route import (
    ExecutionNetworkRoute,
    STATUS_ACTIVE,
    STATUS_DISABLED,
)

from .execution_network_route_error import (
    ExecutionNetworkRouteError,
)


class ExecutionNetworkRoutingService:
    """
    Routes runtime traffic to the healthiest eligible endpoint.

    Composes with:
        endpoint_service: get(endpoint_id) -> object with .runtime_id
            (ExecutionNetworkEndpointService)
        health_service: healthy(endpoint_id) -> bool
            (ExecutionNetworkEndpointHealthService)

    Behavior:
    - register() admits a new ACTIVE route from runtime_id to
      endpoint_id, but only for an endpoint that actually belongs to
      runtime_id
    - resolve() picks the ACTIVE route with the lowest priority value
      among those whose endpoint is currently healthy, skipping every
      other route; a health-check failure is treated the same as an
      unhealthy endpoint; resolving with no eligible route raises
      rather than returning one
    - reroute() re-runs the same selection as resolve(), but only for
      a runtime that has already had a route resolved for it at least
      once
    - disable() is idempotent: disabling an already-disabled route
      simply returns it unchanged; a disabled route is never eligible
      for selection

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, endpoint_service, health_service):
        self._endpoint_service = endpoint_service
        self._health_service = health_service
        self._routes_by_id = {}
        self._resolved_runtimes = set()
        self._lock = RLock()

    def register(self, runtime_id: str, endpoint_id: str, priority: int) -> ExecutionNetworkRoute:
        """
        Register a new route from runtime_id to endpoint_id.

        Raises:
            ExecutionNetworkRouteError: If runtime_id or endpoint_id
                is None or blank, priority is not a non-negative
                integer, endpoint_id is unknown, or it belongs to a
                different runtime
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        endpoint = self._resolve_endpoint(endpoint_id)

        if endpoint.runtime_id != runtime_id:
            raise ExecutionNetworkRouteError(
                f"Cannot register a route for runtime ID {runtime_id!r}: endpoint ID "
                f"{endpoint_id!r} belongs to a different runtime."
            )

        with self._lock:
            route = ExecutionNetworkRoute(
                route_id=str(uuid4()),
                runtime_id=runtime_id,
                endpoint_id=endpoint_id,
                priority=priority,
                status=STATUS_ACTIVE,
            )

            self._routes_by_id[route.route_id] = route

            return route

    def resolve(self, runtime_id: str) -> ExecutionNetworkRoute:
        """
        The ACTIVE route with the lowest priority value among those
        whose endpoint is currently healthy, for runtime_id.

        Raises:
            ExecutionNetworkRouteError: If runtime_id is None or
                blank, or no eligible route is available
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            route = self._select(runtime_id)
            self._resolved_runtimes.add(runtime_id)

            return route

    def reroute(self, runtime_id: str) -> ExecutionNetworkRoute:
        """
        Re-run route selection for runtime_id, picking a new eligible
        route if the previously resolved one is no longer healthy.

        Raises:
            ExecutionNetworkRouteError: If runtime_id is None or
                blank, no route has ever been resolved for it, or no
                eligible route is available
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            if runtime_id not in self._resolved_runtimes:
                raise ExecutionNetworkRouteError(
                    f"Cannot reroute runtime ID {runtime_id!r}: no route has been resolved for it yet."
                )

            return self._select(runtime_id)

    def disable(self, route_id: str) -> ExecutionNetworkRoute:
        """
        Disable a route. Idempotent: disabling an already-disabled
        route simply returns it unchanged.

        Raises:
            ExecutionNetworkRouteError: If route_id is None or blank,
                or no route is registered under it
        """

        self._validate_text(route_id, "route ID")

        with self._lock:
            route = self._resolve_route(route_id)

            if route.status == STATUS_DISABLED:
                return route

            disabled = replace(route, status=STATUS_DISABLED)
            self._routes_by_id[route_id] = disabled

            return disabled

    def _select(self, runtime_id: str) -> ExecutionNetworkRoute:
        candidates = sorted(
            (
                route
                for route in self._routes_by_id.values()
                if route.runtime_id == runtime_id and route.status == STATUS_ACTIVE
            ),
            key=lambda route: route.priority,
        )

        for route in candidates:
            if self._is_healthy(route.endpoint_id):
                return route

        raise ExecutionNetworkRouteError(
            f"No eligible route is available for runtime ID {runtime_id!r}: "
            f"all endpoints are unavailable."
        )

    def _is_healthy(self, endpoint_id: str) -> bool:
        try:
            return bool(self._health_service.healthy(endpoint_id))
        except Exception:
            return False

    def _resolve_endpoint(self, endpoint_id: str):
        try:
            return self._endpoint_service.get(endpoint_id)
        except Exception as error:
            raise ExecutionNetworkRouteError(
                f"Cannot resolve endpoint ID {endpoint_id!r}: it is unknown."
            ) from error

    def _resolve_route(self, route_id: str) -> ExecutionNetworkRoute:
        route = self._routes_by_id.get(route_id)

        if route is None:
            raise ExecutionNetworkRouteError(f"No route is registered under route ID {route_id!r}.")

        return route

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkRouteError(f"Cannot use an empty or blank {field_name}.")
