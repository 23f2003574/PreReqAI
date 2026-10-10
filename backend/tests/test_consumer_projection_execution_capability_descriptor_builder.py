from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder,
)


STANDARD = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD
)
RESTRICTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED
)
UNSUPPORTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED
)


def _make_classification(
    *,
    projection_name="workspace.bootstrap",
    classification=STANDARD,
    profile="EXECUTION_READY",
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationReport(
        projection_name=projection_name,
        classification=classification,
        profile=profile,
        executable=executable,
    )


class TestStandardClassification:
    """STANDARD produces the standard-capability presentation."""

    def test_standard_descriptor(self):
        classification = _make_classification(
            classification=STANDARD,
            profile="EXECUTION_READY",
            executable=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.title == "Standard Capability"
        assert (
            descriptor.description
            == "Projection supports normal execution."
        )


class TestRestrictedClassification:
    """RESTRICTED produces the restricted-capability presentation."""

    def test_restricted_descriptor(self):
        classification = _make_classification(
            classification=RESTRICTED,
            profile="APPROVAL_REQUIRED",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.title == "Restricted Capability"
        assert (
            descriptor.description
            == "Projection requires additional approval before execution."
        )


class TestUnsupportedClassification:
    """UNSUPPORTED produces the unsupported-capability presentation."""

    def test_unsupported_descriptor(self):
        classification = _make_classification(
            classification=UNSUPPORTED,
            profile="EXECUTION_BLOCKED",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.title == "Unsupported Capability"
        assert (
            descriptor.description
            == "Projection is not capable of execution."
        )


class TestProjectionPreserved:
    """projection_name is copied from the classification report."""

    def test_projection_name_is_preserved(self):
        classification = _make_classification(
            projection_name="workspace.attention"
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the classification report, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        classification = _make_classification(
            classification=STANDARD, executable=True
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.executable is True

    def test_executable_flag_false_is_preserved(self):
        classification = _make_classification(
            classification=UNSUPPORTED, executable=False
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.executable is False


class TestClassificationPreserved:
    """classification is copied from the report, not recomputed."""

    def test_classification_is_preserved(self):
        classification = _make_classification(classification=RESTRICTED)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert descriptor.classification == RESTRICTED


class TestDeterminism:
    """Building the same classification report twice yields equal descriptors."""

    def test_equivalent_classification_produces_equivalent_descriptors(
        self,
    ):
        classification = _make_classification(
            classification=RESTRICTED, profile="APPROVAL_REQUIRED"
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )

        first = builder.build(classification)
        second = builder.build(classification)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_classification(self):
        classification = _make_classification(
            classification=RESTRICTED, profile="APPROVAL_REQUIRED"
        )
        classification_dict_before = classification.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        builder.build(classification)

        assert classification.to_dict() == classification_dict_before

    def test_descriptor_carries_no_execution_state(self):
        classification = _make_classification(
            classification=STANDARD, profile="EXECUTION_READY"
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptorBuilder()
        )
        descriptor = builder.build(classification)

        assert set(descriptor.to_dict().keys()) == {
            "projection_name",
            "classification",
            "title",
            "description",
            "executable",
        }
