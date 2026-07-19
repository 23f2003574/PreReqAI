import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    executable=True,
    title="Capability Accepted",
    message="Projection satisfies all execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage(
        projection_name=projection_name,
        decision=decision,
        executable=executable,
        title=title,
        message=message,
    )


def _plan(*, additions=(), updates=(), unchanged=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan(
        additions=tuple(additions),
        updates=tuple(updates),
        unchanged=tuple(unchanged),
    )


class TestEmptyPlan:
    """An empty merge plan validates as trivially valid."""

    def test_empty_plan(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()

        report = validator.validate(_plan())

        assert report.additions == 0
        assert report.updates == 0
        assert report.unchanged == 0
        assert report.duplicate_projection_names == ()
        assert report.is_valid is True


class TestValidPlan:
    """A plan with unique projection names across all collections is valid."""

    def test_valid_plan(self):
        addition = _make_package(projection_name="workspace.export")
        update = _make_package(projection_name="workspace.bootstrap")
        unchanged = _make_package(projection_name="session.actions")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(
                additions=(addition,),
                updates=(update,),
                unchanged=(unchanged,),
            )
        )

        assert report.additions == 1
        assert report.updates == 1
        assert report.unchanged == 1
        assert report.duplicate_projection_names == ()
        assert report.is_valid is True


class TestDuplicateInAdditions:
    """Two additions sharing a projection name are reported as duplicates."""

    def test_duplicate_in_additions(self):
        first = _make_package(projection_name="workspace.bootstrap")
        second = _make_package(projection_name="workspace.bootstrap")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(additions=(first, second))
        )

        assert report.duplicate_projection_names == ("workspace.bootstrap",)
        assert report.is_valid is False


class TestDuplicateInUpdates:
    """Two updates sharing a projection name are reported as duplicates."""

    def test_duplicate_in_updates(self):
        first = _make_package(projection_name="workspace.bootstrap")
        second = _make_package(projection_name="workspace.bootstrap")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(updates=(first, second))
        )

        assert report.duplicate_projection_names == ("workspace.bootstrap",)
        assert report.is_valid is False


class TestDuplicateAcrossCollections:
    """A projection appearing in more than one collection is a duplicate."""

    def test_duplicate_across_collections(self):
        addition = _make_package(projection_name="workspace.bootstrap")
        update = _make_package(projection_name="workspace.bootstrap")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(additions=(addition,), updates=(update,))
        )

        assert report.duplicate_projection_names == ("workspace.bootstrap",)
        assert report.is_valid is False


class TestEmptyProjectionName:
    """An empty projection name is reported and invalidates the plan."""

    def test_empty_projection_name(self):
        package = _make_package(projection_name="")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(additions=(package,))
        )

        assert report.duplicate_projection_names == ("",)
        assert report.is_valid is False


class TestCorrectCounts:
    """Collection sizes are reported accurately regardless of validity."""

    def test_correct_counts(self):
        additions = (
            _make_package(projection_name="workspace.export"),
            _make_package(projection_name="workspace.bootstrap"),
        )
        updates = (
            _make_package(projection_name="workspace.attention"),
        )
        unchanged = (
            _make_package(projection_name="session.actions"),
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(
                additions=additions,
                updates=updates,
                unchanged=unchanged,
            )
        )

        assert report.additions == 2
        assert report.updates == 1
        assert report.unchanged == 1


class TestValidityFlag:
    """is_valid tracks the presence of duplicate/empty projection names exactly."""

    def test_is_valid_true_when_no_duplicates(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()

        report = validator.validate(
            _plan(additions=(_make_package(),))
        )

        assert report.is_valid is True

    def test_is_valid_false_when_duplicates_present(self):
        first = _make_package(projection_name="workspace.bootstrap")
        second = _make_package(projection_name="workspace.bootstrap")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        report = validator.validate(
            _plan(additions=(first,), updates=(second,))
        )

        assert report.is_valid is False


class TestPlanUnchanged:
    """Validation never mutates the merge plan or its packages."""

    def test_plan_remains_unchanged(self):
        package = _make_package()
        plan = _plan(additions=(package,))
        package_dict = package.to_dict()

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()
        validator.validate(plan)

        assert plan.additions == (package,)
        assert plan.updates == ()
        assert plan.unchanged == ()
        assert package.to_dict() == package_dict


class TestInvalidPlan:
    """A None or non-plan value is rejected."""

    def test_reject_none_plan(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError
        ):
            validator.validate(None)

    def test_reject_non_plan_object(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError
        ):
            validator.validate(object())


class TestDeterminism:
    """Validating the same merge plan twice agrees."""

    def test_repeated_validation_is_deterministic(self):
        plan = _plan(additions=(_make_package(),))
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidator()

        first = validator.validate(plan)
        second = validator.validate(plan)

        assert first == second
