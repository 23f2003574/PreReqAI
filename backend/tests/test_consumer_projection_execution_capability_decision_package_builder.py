import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW
REJECT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT

STANDARD_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.STANDARD_CAPABILITY
)
RESTRICTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.RESTRICTED_CAPABILITY
)
UNSUPPORTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.UNSUPPORTED_CAPABILITY
)


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    reason=STANDARD_CAPABILITY,
    executable=True,
    title="Capability Accepted",
    description="Projection satisfies execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        executable=executable,
        title=title,
        description=description,
    )


def _make_response(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    executable=True,
    title="Capability Accepted",
    message="Projection satisfies all execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse(
        projection_name=projection_name,
        decision=decision,
        executable=executable,
        title=title,
        message=message,
    )


class TestPackageBuilding:
    """A valid, aligned pair builds a package."""

    def test_package_builds_successfully(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.projection_name == "workspace.bootstrap"
        assert package.decision == ACCEPT
        assert package.executable is True
        assert package.title == "Capability Accepted"
        assert (
            package.message
            == "Projection satisfies all execution capability requirements."
        )


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        snapshot = _make_snapshot(projection_name="workspace.bootstrap")
        response = _make_response(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError
        ):
            builder.build(snapshot, response)


class TestDecisionMismatch:
    """Artifacts disagreeing on the resolved decision are rejected."""

    def test_decision_mismatch_raises_error(self):
        snapshot = _make_snapshot(decision=ACCEPT, reason=STANDARD_CAPABILITY)
        response = _make_response(
            decision=REVIEW,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError
        ):
            builder.build(snapshot, response)


class TestExecutableMismatch:
    """Artifacts disagreeing on executability are rejected."""

    def test_executable_mismatch_raises_error(self):
        snapshot = _make_snapshot(decision=ACCEPT, executable=True)
        response = _make_response(decision=ACCEPT, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError
        ):
            builder.build(snapshot, response)


class TestTitlePreserved:
    """title is copied from the consumer response."""

    def test_title_is_preserved(self):
        snapshot = _make_snapshot()
        response = _make_response(title="Capability Accepted")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.title == "Capability Accepted"


class TestMessagePreserved:
    """message is copied from the consumer response."""

    def test_message_is_preserved(self):
        snapshot = _make_snapshot()
        response = _make_response(
            message="Projection satisfies all execution capability requirements."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert (
            package.message
            == "Projection satisfies all execution capability requirements."
        )


class TestDeterminism:
    """Building the same pair twice yields equal packages."""

    def test_equivalent_inputs_produce_equivalent_packages(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )

        first = builder.build(snapshot, response)
        second = builder.build(snapshot, response)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        snapshot = _make_snapshot()
        response = _make_response()

        snapshot_dict = snapshot.to_dict()
        response_dict = response.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )
        builder.build(snapshot, response)

        assert snapshot.to_dict() == snapshot_dict
        assert response.to_dict() == response_dict

    def test_package_carries_no_scheduler_or_persistence_state(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert set(package.to_dict().keys()) == {
            "projection_name",
            "decision",
            "executable",
            "title",
            "message",
        }
