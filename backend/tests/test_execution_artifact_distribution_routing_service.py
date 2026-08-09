import pytest

from backend.session import (
    ArtifactDistributionRoute,
    ExecutionArtifactDistributionChannel,
    ExecutionArtifactDistributionRoutingError as Error,
    ExecutionArtifactDistributionRoutingService,
    ExecutionArtifactDistributionService,
)


class _UnusedArtifactRegistry:
    def get(self, artifact_id):
        raise AssertionError("execution artifact registry should not be used in routing tests")


def _build():
    distribution_service = ExecutionArtifactDistributionService(_UnusedArtifactRegistry())
    routing_service = ExecutionArtifactDistributionRoutingService(distribution_service)
    return distribution_service, routing_service


def _channel(channel_id):
    return ExecutionArtifactDistributionChannel(
        channel_id=channel_id,
        name=f"Channel {channel_id}",
        type="webhook",
        endpoint=f"https://example.test/hooks/{channel_id}",
    )


def _route(route_id, artifact_type="log", channel_id="channel-1", priority=0, enabled=True):
    return ArtifactDistributionRoute(
        route_id=route_id,
        artifact_type=artifact_type,
        channel_id=channel_id,
        priority=priority,
        enabled=enabled,
    )


class TestExecutionArtifactDistributionRoutingService:
    def test_add_and_remove_route(self):
        distribution_service, routing_service = _build()
        distribution_service.register(_channel("channel-1"))

        added = routing_service.add(_route("route-1", channel_id="channel-1"))

        assert isinstance(added, ArtifactDistributionRoute)
        assert added in routing_service.routes("log")

        removed = routing_service.remove("route-1")

        assert removed.route_id == "route-1"
        assert routing_service.routes("log") == []

    def test_priority_resolution(self):
        distribution_service, routing_service = _build()
        distribution_service.register(_channel("channel-1"))
        distribution_service.register(_channel("channel-2"))

        routing_service.add(_route("route-low", channel_id="channel-1", priority=1))
        routing_service.add(_route("route-high", channel_id="channel-2", priority=5))

        resolved = routing_service.resolve("log")

        assert resolved.route_id == "route-high"
        assert resolved.channel_id == "channel-2"

    def test_disabled_route_ignored(self):
        distribution_service, routing_service = _build()
        distribution_service.register(_channel("channel-1"))
        distribution_service.register(_channel("channel-2"))

        routing_service.add(_route("route-disabled", channel_id="channel-1", priority=9, enabled=False))
        routing_service.add(_route("route-enabled", channel_id="channel-2", priority=1))

        resolved = routing_service.resolve("log")

        assert resolved.route_id == "route-enabled"

    def test_unknown_channel_rejection(self):
        _distribution_service, routing_service = _build()

        with pytest.raises(Error):
            routing_service.add(_route("route-1", channel_id="unknown-channel"))

    def test_deterministic_ordering(self):
        distribution_service, routing_service = _build()
        distribution_service.register(_channel("channel-1"))
        distribution_service.register(_channel("channel-2"))

        routing_service.add(_route("route-first", channel_id="channel-1", priority=3))
        routing_service.add(_route("route-second", channel_id="channel-2", priority=3))

        first_resolution = routing_service.resolve("log")
        second_resolution = routing_service.resolve("log")

        assert first_resolution.route_id == "route-first"
        assert second_resolution.route_id == "route-first"
