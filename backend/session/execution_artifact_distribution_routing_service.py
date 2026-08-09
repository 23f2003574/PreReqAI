from threading import (
    RLock,
)

from .artifact_distribution_route import (
    ArtifactDistributionRoute,
)

from .execution_artifact_distribution_routing_error import (
    ExecutionArtifactDistributionRoutingError,
)


class ExecutionArtifactDistributionRoutingService:
    """
    Routes artifacts to the distribution channel that should receive
    them, based on explicit routing rules keyed by artifact type,
    using an existing execution artifact distribution service to
    confirm a route's channel is genuinely known before it is added.

    The service's responsibility is routing rule bookkeeping and
    resolution only. It does not publish artifacts to a channel
    itself.

    Behavior:
    - A route ID is unique: add() rejects a route ID that is already
      registered
    - An artifact type may have any number of routes; resolve()
      considers only its enabled routes and picks the one with the
      highest priority
    - resolve() is deterministic: when multiple enabled routes for an
      artifact type share the highest priority, the one added first
      wins
    - routes() lists every route registered for an artifact type, in
      the order they were added, regardless of enabled state

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_distribution_service):
        """
        Args:
            execution_artifact_distribution_service: The service used
                to confirm a route's channel ID is known before the
                route is added. Any object exposing `channels()`,
                returning an iterable of objects with a `.channel_id`,
                is accepted
        """

        self._execution_artifact_distribution_service = execution_artifact_distribution_service
        self._routes_by_id = {}
        self._route_ids_by_artifact_type = {}
        self._lock = RLock()

    def add(self, route: ArtifactDistributionRoute) -> ArtifactDistributionRoute:
        """
        Add a new routing rule.

        Raises:
            ExecutionArtifactDistributionRoutingError: If route is not
                an ArtifactDistributionRoute, its route ID is already
                registered, or its channel ID is not known to the
                execution artifact distribution service
        """

        if not isinstance(route, ArtifactDistributionRoute):
            raise ExecutionArtifactDistributionRoutingError(
                "Cannot add an invalid route: route must be an ArtifactDistributionRoute."
            )

        with self._lock:
            if route.route_id in self._routes_by_id:
                raise ExecutionArtifactDistributionRoutingError(
                    f"Route ID {route.route_id!r} is already registered."
                )

            self._ensure_channel_known(route.channel_id)

            self._routes_by_id[route.route_id] = route
            self._route_ids_by_artifact_type.setdefault(route.artifact_type, []).append(route.route_id)

            return route

    def remove(self, route_id: str) -> ArtifactDistributionRoute:
        """
        Remove a routing rule.

        Raises:
            ExecutionArtifactDistributionRoutingError: If route_id is
                None or blank, or no route is registered under it
        """

        self._validate_id(route_id, "route ID")

        with self._lock:
            route = self._resolve(route_id)

            del self._routes_by_id[route_id]
            self._route_ids_by_artifact_type[route.artifact_type].remove(route_id)

            return route

    def resolve(self, artifact_type: str) -> ArtifactDistributionRoute:
        """
        Resolve which route an artifact of a given type should be
        distributed through: the enabled route for artifact_type with
        the highest priority, the earliest added winning any tie.

        Raises:
            ExecutionArtifactDistributionRoutingError: If
                artifact_type is None or blank, or no enabled route
                is registered for it
        """

        self._validate_id(artifact_type, "artifact type")

        with self._lock:
            candidates = [route for route in self._list(artifact_type) if route.enabled]

            if not candidates:
                raise ExecutionArtifactDistributionRoutingError(
                    f"No enabled route is registered for artifact type {artifact_type!r}."
                )

            return max(candidates, key=lambda route: route.priority)

    def routes(self, artifact_type: str) -> list:
        """
        List every route registered for an artifact type, in the
        order they were added, regardless of enabled state.

        Raises:
            ExecutionArtifactDistributionRoutingError: If
                artifact_type is None or blank
        """

        self._validate_id(artifact_type, "artifact type")

        with self._lock:
            return self._list(artifact_type)

    def _list(self, artifact_type: str) -> list:
        return [self._routes_by_id[route_id] for route_id in self._route_ids_by_artifact_type.get(artifact_type, [])]

    def _resolve(self, route_id: str) -> ArtifactDistributionRoute:
        route = self._routes_by_id.get(route_id)

        if route is None:
            raise ExecutionArtifactDistributionRoutingError(f"No route is registered under route ID {route_id!r}.")

        return route

    def _ensure_channel_known(self, channel_id: str) -> None:
        known_channel_ids = {
            channel.channel_id for channel in self._execution_artifact_distribution_service.channels()
        }

        if channel_id not in known_channel_ids:
            raise ExecutionArtifactDistributionRoutingError(
                f"No distribution channel is known under channel ID {channel_id!r}."
            )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionRoutingError(f"Cannot use an empty or blank {field_name}.")
