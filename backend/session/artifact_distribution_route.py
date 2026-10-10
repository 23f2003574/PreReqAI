from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_routing_error import (
    ExecutionArtifactDistributionRoutingError,
)


@dataclass(frozen=True)
class ArtifactDistributionRoute:
    """
    Immutable rule directing artifacts of a given type to a specific
    distribution channel.

    The route is a value object only. It performs no routing of its
    own; adding, removing, and resolving routes is the responsibility
    of an execution artifact distribution routing service.

    Attributes:
        route_id: The route's unique identifier
        artifact_type: The kind of artifact this route applies to,
            e.g. "log" or "report"
        channel_id: The identifier of the distribution channel
            artifacts of artifact_type are routed to
        priority: The route's precedence among other routes for the
            same artifact_type; a higher value wins
        enabled: Whether the route currently participates in
            resolution
    """

    route_id: str

    artifact_type: str

    channel_id: str

    priority: int

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.route_id, "route ID")
        self._require_text(self.artifact_type, "artifact type")
        self._require_text(self.channel_id, "channel ID")

        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ExecutionArtifactDistributionRoutingError(
                "Cannot build a distribution route with a non-integer priority."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionArtifactDistributionRoutingError(
                "Cannot build a distribution route with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionRoutingError(
                f"Cannot build a distribution route with an empty or blank {field_name}."
            )
