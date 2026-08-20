from backend.session import (
    ExecutionArtifactDecision,
    ExecutionArtifactDistributionFailoverService,
    ExecutionArtifactGarbageCollectionService,
    ExecutionArtifactOrchestrationService,
    ExecutionArtifactRegistryService,
    ExecutionArtifactReleaseChannelService,
    WorkspaceExecutionArtifactDistributionService,
    WorkspaceExecutionArtifactIntegrityService,
    WorkspaceExecutionArtifactPromotionService,
    WorkspaceExecutionArtifactRetentionService,
    WorkspaceExecutionArtifactVersionService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeRuntimeStateService:
    def __init__(self, known_runtimes=None):
        self._known_runtimes = set(known_runtimes or ())

    def state(self, runtime_id):
        if runtime_id not in self._known_runtimes:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord("RUNNING")


class _VersionResolver:
    def __init__(self):
        self._versions = {}

    def add(self, version):
        self._versions[version.version_id] = version

    def resolve(self, version_id):
        if version_id not in self._versions:
            raise ValueError(f"unknown version {version_id!r}")

        return self._versions[version_id]


class _IntegrityChecksumProvider:
    def __init__(self):
        self._checksums = {}

    def checksum(self, version_id):
        return self._checksums[version_id]

    def set_checksum(self, version_id, checksum):
        self._checksums[version_id] = checksum


class _DistributionChecksumProvider:
    def __init__(self):
        self._checksums = {}

    def checksum(self, version_id, target):
        return self._checksums[(version_id, target)]

    def set_checksum(self, version_id, target, checksum):
        self._checksums[(version_id, target)] = checksum


def _build():
    runtime_state_service = _FakeRuntimeStateService({"runtime-1"})
    registry = ExecutionArtifactRegistryService(runtime_state_service)
    version_service = WorkspaceExecutionArtifactVersionService(registry)
    resolver = _VersionResolver()

    integrity_checksum_provider = _IntegrityChecksumProvider()
    integrity_service = WorkspaceExecutionArtifactIntegrityService(resolver, integrity_checksum_provider)

    promotion_service = WorkspaceExecutionArtifactPromotionService(registry, integrity_service)

    retention_service = WorkspaceExecutionArtifactRetentionService(registry, resolver, promotion_service)

    distribution_checksum_provider = _DistributionChecksumProvider()
    distribution_service = WorkspaceExecutionArtifactDistributionService(
        integrity_service, promotion_service, resolver, distribution_checksum_provider
    )

    failover_service = ExecutionArtifactDistributionFailoverService(integrity_service, distribution_service)

    garbage_collection_service = ExecutionArtifactGarbageCollectionService(
        version_service, resolver, retention_service, promotion_service
    )

    release_channel_service = ExecutionArtifactReleaseChannelService(integrity_service)

    orchestration = ExecutionArtifactOrchestrationService(
        integrity_service,
        promotion_service,
        distribution_service,
        failover_service,
        release_channel_service,
        garbage_collection_service,
        resolver,
    )

    return {
        "registry": registry,
        "version_service": version_service,
        "resolver": resolver,
        "integrity_checksum_provider": integrity_checksum_provider,
        "distribution_checksum_provider": distribution_checksum_provider,
        "failover_service": failover_service,
        "orchestration": orchestration,
    }


def _register_verified_version(env, checksum="sha256:one"):
    artifact = env["registry"].register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")
    version = env["version_service"].create(artifact.artifact_id, "/artifacts/model-v1.bin", checksum)
    env["resolver"].add(version)
    env["integrity_checksum_provider"].set_checksum(version.version_id, checksum)

    return artifact, version


class TestExecutionArtifactOrchestrationService:
    def test_successful_publication(self):
        env = _build()
        artifact, version = _register_verified_version(env)

        decision = env["orchestration"].publish(artifact.artifact_id, version.version_id)

        assert isinstance(decision, ExecutionArtifactDecision)
        assert decision.action == "PUBLISH"
        assert decision.allowed is True
        assert env["orchestration"].decision(artifact.artifact_id, version.version_id) == decision

    def test_integrity_rejection(self):
        env = _build()
        artifact, version = _register_verified_version(env)
        env["integrity_checksum_provider"].set_checksum(version.version_id, "sha256:tampered")

        decision = env["orchestration"].publish(artifact.artifact_id, version.version_id)

        assert decision.allowed is False
        assert "integrity" in decision.reason

    def test_promotion_gating(self):
        env = _build()
        artifact, version = _register_verified_version(env)

        first = env["orchestration"].promote(artifact.artifact_id, version.version_id, "STAGING")
        assert first.allowed is True
        assert first.action == "PROMOTE"

        blocked = env["orchestration"].promote(artifact.artifact_id, version.version_id, "STAGING")
        assert blocked.allowed is False

        backward = env["orchestration"].promote(artifact.artifact_id, version.version_id, "DEV")
        assert backward.allowed is False

    def test_distribution_failover(self):
        env = _build()
        artifact, version = _register_verified_version(env)
        env["failover_service"].register(artifact.artifact_id, version.version_id, ["us-east", "eu-west"])
        env["distribution_checksum_provider"].set_checksum(version.version_id, "us-east", "sha256:tampered")
        env["distribution_checksum_provider"].set_checksum(version.version_id, "eu-west", "sha256:one")

        decision = env["orchestration"].distribute(artifact.artifact_id, version.version_id)

        assert decision.allowed is True
        assert decision.action == "DISTRIBUTE"
        assert "eu-west" in decision.reason

    def test_release_channel_validation(self):
        env = _build()
        artifact, version = _register_verified_version(env)

        blocked = env["orchestration"].release(artifact.artifact_id, version.version_id, "CANARY")
        assert blocked.allowed is False

        env["failover_service"].register(artifact.artifact_id, version.version_id, ["us-east"])
        env["distribution_checksum_provider"].set_checksum(version.version_id, "us-east", "sha256:one")
        env["orchestration"].distribute(artifact.artifact_id, version.version_id)

        allowed = env["orchestration"].release(artifact.artifact_id, version.version_id, "CANARY")
        assert allowed.allowed is True
        assert allowed.action == "RELEASE"

    def test_retirement_protection(self):
        env = _build()
        artifact, version = _register_verified_version(env)

        decision = env["orchestration"].retire(version.version_id)

        assert decision.allowed is False
        assert decision.action == "RETIRE"
        assert decision.artifact_id == artifact.artifact_id

    def test_deterministic_decision(self):
        env = _build()
        artifact, version = _register_verified_version(env)

        first = env["orchestration"].publish(artifact.artifact_id, version.version_id)
        second = env["orchestration"].publish(artifact.artifact_id, version.version_id)

        assert first.allowed == second.allowed
        assert first.reason == second.reason
        assert first.action == second.action
