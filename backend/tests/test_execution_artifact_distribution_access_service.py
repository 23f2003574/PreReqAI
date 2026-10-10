from backend.session import (
    ArtifactAccessResult,
    ArtifactDistributionPermission,
    ExecutionArtifactDistributionAccessService,
    ExecutionArtifactDistributionChannel,
    ExecutionArtifactDistributionService,
)


class _UnusedArtifactRegistry:
    def get(self, artifact_id):
        raise AssertionError("execution artifact registry should not be used in access control tests")


def _build():
    distribution_service = ExecutionArtifactDistributionService(_UnusedArtifactRegistry())
    access_service = ExecutionArtifactDistributionAccessService(distribution_service)
    return distribution_service, access_service


def _channel(channel_id="channel-1"):
    return ExecutionArtifactDistributionChannel(
        channel_id=channel_id,
        name=f"Channel {channel_id}",
        type="webhook",
        endpoint=f"https://example.test/hooks/{channel_id}",
    )


class TestExecutionArtifactDistributionAccessService:
    def test_grant_and_authorize(self):
        distribution_service, access_service = _build()
        distribution_service.register(_channel())

        granted = access_service.grant("channel-1", "log", "PUBLISH")

        assert isinstance(granted, ArtifactDistributionPermission)
        assert granted.operation == "PUBLISH"

        result = access_service.authorize("channel-1", "log", "PUBLISH")

        assert isinstance(result, ArtifactAccessResult)
        assert result.allowed is True

    def test_default_denial(self):
        distribution_service, access_service = _build()
        distribution_service.register(_channel())

        result = access_service.authorize("channel-1", "log", "PUBLISH")

        assert isinstance(result, ArtifactAccessResult)
        assert result.allowed is False

    def test_revoke(self):
        distribution_service, access_service = _build()
        distribution_service.register(_channel())

        permission = access_service.grant("channel-1", "log", "PUBLISH")
        assert access_service.authorize("channel-1", "log", "PUBLISH").allowed is True

        access_service.revoke(permission.permission_id)
        assert access_service.authorize("channel-1", "log", "PUBLISH").allowed is False

    def test_type_isolation(self):
        distribution_service, access_service = _build()
        distribution_service.register(_channel())

        access_service.grant("channel-1", "log", "PUBLISH")

        assert access_service.authorize("channel-1", "log", "PUBLISH").allowed is True
        assert access_service.authorize("channel-1", "report", "PUBLISH").allowed is False

    def test_permission_listing(self):
        distribution_service, access_service = _build()
        distribution_service.register(_channel())

        access_service.grant("channel-1", "log", "PUBLISH")
        access_service.grant("channel-1", "report", "READ")

        listed = access_service.permissions("channel-1")

        assert [(entry.artifact_type, entry.operation) for entry in listed] == [
            ("log", "PUBLISH"),
            ("report", "READ"),
        ]
