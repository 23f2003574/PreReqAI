from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW


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


def _snapshot(*packages):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshot(
        packages=tuple(
            sorted(packages, key=lambda package: package.projection_name)
        ),
    )


class TestEmptySnapshots:
    """Diffing two empty snapshots produces an empty diff."""

    def test_empty_snapshots(self):
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(_snapshot(), _snapshot())

        assert diff.added == ()
        assert diff.removed == ()
        assert diff.modified == ()


class TestAddedProjection:
    """A projection only in current is reported as added."""

    def test_added_projection(self):
        package = _make_package()
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(_snapshot(), _snapshot(package))

        assert diff.added == (package,)
        assert diff.removed == ()
        assert diff.modified == ()


class TestRemovedProjection:
    """A projection only in previous is reported as removed."""

    def test_removed_projection(self):
        package = _make_package()
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(_snapshot(package), _snapshot())

        assert diff.added == ()
        assert diff.removed == (package,)
        assert diff.modified == ()


class TestModifiedProjection:
    """A projection in both, with a differing package, is reported as modified."""

    def test_modified_projection(self):
        old_package = _make_package(decision=ACCEPT, title="Capability Accepted")
        new_package = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(_snapshot(old_package), _snapshot(new_package))

        assert diff.added == ()
        assert diff.removed == ()
        assert diff.modified == (new_package,)


class TestUnchangedProjectionIgnored:
    """An identical projection in both snapshots produces no diff entry."""

    def test_unchanged_projection_ignored(self):
        package = _make_package()
        same_package = _make_package()
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(_snapshot(package), _snapshot(same_package))

        assert diff.added == ()
        assert diff.removed == ()
        assert diff.modified == ()


class TestMultipleSimultaneousChanges:
    """Added, removed, and modified projections can all appear in one diff."""

    def test_multiple_simultaneous_changes(self):
        unchanged = _make_package(projection_name="session.actions")
        removed = _make_package(projection_name="workspace.attention")
        old_modified = _make_package(
            projection_name="workspace.bootstrap",
            decision=ACCEPT,
        )
        new_modified = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        added = _make_package(projection_name="workspace.export")

        previous = _snapshot(unchanged, removed, old_modified)
        current = _snapshot(unchanged, new_modified, added)

        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()
        diff = engine.diff(previous, current)

        assert diff.added == (added,)
        assert diff.removed == (removed,)
        assert diff.modified == (new_modified,)


class TestAlphabeticalOrdering:
    """Each collection is sorted alphabetically by projection_name."""

    def test_added_is_alphabetically_sorted(self):
        added_a = _make_package(projection_name="a.projection")
        added_b = _make_package(projection_name="b.projection")
        added_c = _make_package(projection_name="c.projection")

        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()
        diff = engine.diff(
            _snapshot(),
            _snapshot(added_c, added_a, added_b),
        )

        assert diff.added == (added_a, added_b, added_c)


class TestImmutableOutput:
    """All diff collections are immutable tuples."""

    def test_diff_collections_are_tuples(self):
        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        diff = engine.diff(
            _snapshot(),
            _snapshot(_make_package()),
        )

        assert isinstance(diff.added, tuple)
        assert isinstance(diff.removed, tuple)
        assert isinstance(diff.modified, tuple)


class TestInputsUnchanged:
    """Diffing never mutates either snapshot or its packages."""

    def test_snapshots_and_packages_unchanged(self):
        old_package = _make_package(decision=ACCEPT)
        new_package = _make_package(decision=REVIEW, executable=False)
        previous = _snapshot(old_package)
        current = _snapshot(new_package)

        old_dict = old_package.to_dict()
        new_dict = new_package.to_dict()

        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()
        engine.diff(previous, current)

        assert previous.packages == (old_package,)
        assert current.packages == (new_package,)
        assert old_package.to_dict() == old_dict
        assert new_package.to_dict() == new_dict


class TestDeterminism:
    """Diffing the same pair of snapshots twice produces equal diffs."""

    def test_repeated_diff_is_deterministic(self):
        previous = _snapshot(_make_package(decision=ACCEPT))
        current = _snapshot(_make_package(decision=REVIEW, executable=False))

        engine = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryDiffEngine()

        first = engine.diff(previous, current)
        second = engine.diff(previous, current)

        assert first == second
