import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactDistributionPolicy,
    ExecutionArtifactDistributionPolicyAssignment,
    ExecutionArtifactDistributionPolicyError as Error,
    ExecutionArtifactDistributionPolicyService,
    ExecutionArtifactEncryptionService,
    ExecutionArtifactIntegrityService,
    ExecutionArtifactService,
    ExecutionArtifactSigningService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    encryption_service = ExecutionArtifactEncryptionService(artifact_service)
    signing_service = ExecutionArtifactSigningService(artifact_service)
    integrity_service = ExecutionArtifactIntegrityService()
    policy_service = ExecutionArtifactDistributionPolicyService(
        artifact_service,
        encryption_service,
        signing_service,
        integrity_service,
    )

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return {
        "artifact_service": artifact_service,
        "encryption_service": encryption_service,
        "signing_service": signing_service,
        "integrity_service": integrity_service,
        "policy_service": policy_service,
        "session": session,
    }


def _register_artifact(env, artifact_id="artifact-1", type_="log"):
    return env["artifact_service"].register(
        env["session"].session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=env["session"].session_id,
            name=f"{artifact_id}.log",
            type=type_,
            location=f"/tmp/{artifact_id}.log",
        ),
    )


def _policy(policy_id="policy-1", allowed_types=("log",), **requirements):
    return ExecutionArtifactDistributionPolicy(
        policy_id=policy_id,
        allowed_types=frozenset(allowed_types),
        **requirements,
    )


class TestExecutionArtifactDistributionPolicyService:
    def test_register_and_assign_policy(self):
        env = _build()

        registered = env["policy_service"].register(_policy())
        assert isinstance(registered, ExecutionArtifactDistributionPolicy)

        assignment = env["policy_service"].assign("policy-1", "channel-1")
        assert isinstance(assignment, ExecutionArtifactDistributionPolicyAssignment)
        assert assignment.policy_id == "policy-1"
        assert assignment.channel_id == "channel-1"

    def test_compliant_artifact(self):
        env = _build()
        artifact = _register_artifact(env)
        env["encryption_service"].encrypt(artifact.artifact_id, "key-1")
        env["signing_service"].sign(artifact.artifact_id, "key-1")
        env["integrity_service"].record(artifact.artifact_id, "checksum-1")

        env["policy_service"].register(
            _policy(require_encryption=True, require_signature=True, require_integrity=True)
        )
        env["policy_service"].assign("policy-1", "channel-1")

        assert env["policy_service"].validate(artifact.artifact_id, "channel-1") is True

    def test_encryption_rejection(self):
        env = _build()
        artifact = _register_artifact(env)
        env["signing_service"].sign(artifact.artifact_id, "key-1")
        env["integrity_service"].record(artifact.artifact_id, "checksum-1")

        env["policy_service"].register(_policy(require_encryption=True))
        env["policy_service"].assign("policy-1", "channel-1")

        with pytest.raises(Error):
            env["policy_service"].validate(artifact.artifact_id, "channel-1")

    def test_signature_rejection(self):
        env = _build()
        artifact = _register_artifact(env)
        env["encryption_service"].encrypt(artifact.artifact_id, "key-1")
        env["integrity_service"].record(artifact.artifact_id, "checksum-1")

        env["policy_service"].register(_policy(require_signature=True))
        env["policy_service"].assign("policy-1", "channel-1")

        with pytest.raises(Error):
            env["policy_service"].validate(artifact.artifact_id, "channel-1")

    def test_integrity_rejection(self):
        env = _build()
        artifact = _register_artifact(env)
        env["encryption_service"].encrypt(artifact.artifact_id, "key-1")
        env["signing_service"].sign(artifact.artifact_id, "key-1")

        env["policy_service"].register(_policy(require_integrity=True))
        env["policy_service"].assign("policy-1", "channel-1")

        with pytest.raises(Error):
            env["policy_service"].validate(artifact.artifact_id, "channel-1")

    def test_channel_policy_lookup(self):
        env = _build()
        env["policy_service"].register(_policy())
        env["policy_service"].assign("policy-1", "channel-1")

        policy = env["policy_service"].policy("channel-1")

        assert policy.policy_id == "policy-1"

        with pytest.raises(Error):
            env["policy_service"].policy("channel-2")
