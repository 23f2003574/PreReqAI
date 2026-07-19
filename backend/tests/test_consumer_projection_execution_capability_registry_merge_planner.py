from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner,
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
    """Planning between two empty snapshots produces an empty plan."""

    def test_empty_snapshots(self):
        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        plan = planner.plan(_snapshot(), _snapshot())

        assert plan.additions == ()
        assert plan.updates == ()
        assert plan.unchanged == ()


class TestAdditionDetected:
    """A projection only in incoming is planned as an addition."""

    def test_addition_detected(self):
        package = _make_package()
        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        plan = planner.plan(_snapshot(), _snapshot(package))

        assert plan.additions == (package,)
        assert plan.updates == ()
        assert plan.unchanged == ()


class TestUpdateDetected:
    """A projection in both with a differing package is planned as an update."""

    def test_update_detected(self):
        base_package = _make_package(decision=ACCEPT, title="Capability Accepted")
        incoming_package = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        plan = planner.plan(_snapshot(base_package), _snapshot(incoming_package))

        assert plan.additions == ()
        assert plan.updates == (incoming_package,)
        assert plan.unchanged == ()


class TestUnchangedDetected:
    """A projection in both with an identical package is planned as unchanged."""

    def test_unchanged_detected(self):
        base_package = _make_package()
        incoming_package = _make_package()
        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        plan = planner.plan(_snapshot(base_package), _snapshot(incoming_package))

        assert plan.additions == ()
        assert plan.updates == ()
        assert plan.unchanged == (incoming_package,)


class TestMultipleOperations:
    """Additions, updates, and unchanged entries can all appear in one plan."""

    def test_multiple_operations(self):
        unchanged = _make_package(projection_name="session.actions")
        base_update = _make_package(
            projection_name="workspace.bootstrap",
            decision=ACCEPT,
        )
        incoming_update = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        addition = _make_package(projection_name="workspace.export")

        base = _snapshot(unchanged, base_update)
        incoming = _snapshot(unchanged, incoming_update, addition)

        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()
        plan = planner.plan(base, incoming)

        assert plan.additions == (addition,)
        assert plan.updates == (incoming_update,)
        assert plan.unchanged == (unchanged,)


class TestAlphabeticalOrdering:
    """Each collection is sorted alphabetically by projection_name."""

    def test_additions_are_alphabetically_sorted(self):
        addition_a = _make_package(projection_name="a.projection")
        addition_b = _make_package(projection_name="b.projection")
        addition_c = _make_package(projection_name="c.projection")

        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()
        plan = planner.plan(
            _snapshot(),
            _snapshot(addition_c, addition_a, addition_b),
        )

        assert plan.additions == (addition_a, addition_b, addition_c)


class TestImmutableOutput:
    """All merge plan collections are immutable tuples."""

    def test_plan_collections_are_tuples(self):
        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        plan = planner.plan(
            _snapshot(),
            _snapshot(_make_package()),
        )

        assert isinstance(plan.additions, tuple)
        assert isinstance(plan.updates, tuple)
        assert isinstance(plan.unchanged, tuple)


class TestInputsUnchanged:
    """Planning never mutates either snapshot or its packages."""

    def test_snapshots_and_packages_unchanged(self):
        base_package = _make_package(decision=ACCEPT)
        incoming_package = _make_package(decision=REVIEW, executable=False)
        base = _snapshot(base_package)
        incoming = _snapshot(incoming_package)

        base_dict = base_package.to_dict()
        incoming_dict = incoming_package.to_dict()

        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()
        planner.plan(base, incoming)

        assert base.packages == (base_package,)
        assert incoming.packages == (incoming_package,)
        assert base_package.to_dict() == base_dict
        assert incoming_package.to_dict() == incoming_dict


class TestIdenticalSnapshots:
    """Two identical snapshots produce only unchanged entries."""

    def test_identical_snapshots(self):
        package_a = _make_package(projection_name="session.actions")
        package_b = _make_package(projection_name="workspace.bootstrap")

        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()
        plan = planner.plan(
            _snapshot(package_a, package_b),
            _snapshot(package_a, package_b),
        )

        assert plan.additions == ()
        assert plan.updates == ()
        assert plan.unchanged == (package_a, package_b)


class TestDeterminism:
    """Planning the same pair of snapshots twice produces equal plans."""

    def test_repeated_planning_is_deterministic(self):
        base = _snapshot(_make_package(decision=ACCEPT))
        incoming = _snapshot(_make_package(decision=REVIEW, executable=False))

        planner = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlanner()

        first = planner.plan(base, incoming)
        second = planner.plan(base, incoming)

        assert first == second
