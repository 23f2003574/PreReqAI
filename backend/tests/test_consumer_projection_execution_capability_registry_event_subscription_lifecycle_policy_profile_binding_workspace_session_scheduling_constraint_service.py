from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint as Constraint,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintService as ConstraintService,
)


def _at(minutes):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _capacity(constraint_id, current, limit, enabled=True):
    return Constraint(
        constraint_id=constraint_id,
        type="capacity",
        configuration={"current": current, "limit": limit},
        enabled=enabled,
    )


def _predicate(constraint_id, fn, enabled=True):
    return Constraint(
        constraint_id=constraint_id,
        type="predicate",
        configuration={"predicate": fn},
        enabled=enabled,
    )


class TestWorkspaceSessionSchedulingConstraintService:
    def test_register_constraint(self):
        service = ConstraintService()
        constraint = _capacity("constraint-1", current=1, limit=5)

        registered = service.register(constraint)

        assert isinstance(registered, Constraint)
        assert registered.constraint_id == "constraint-1"

        with pytest.raises(Error):
            service.register(constraint)

    def test_assign_constraint(self):
        service = ConstraintService()
        service.register(_capacity("constraint-1", current=1, limit=5))

        service.assign("schedule-1", "constraint-1")

        with pytest.raises(Error):
            service.assign("schedule-1", "constraint-1")

        with pytest.raises(Error):
            service.assign("schedule-2", "unknown-constraint")

    def test_successful_evaluation(self):
        service = ConstraintService()
        service.register(_capacity("constraint-1", current=1, limit=5))
        service.assign("schedule-1", "constraint-1")

        result = service.evaluate("schedule-1")

        assert isinstance(result, Result)
        assert result.satisfied is True
        assert result.violations == ()

        # a schedule with no constraints assigned is vacuously satisfied
        result = service.evaluate("schedule-without-constraints")
        assert result.satisfied is True
        assert result.violations == ()

    def test_blocking_constraint(self):
        service = ConstraintService()
        service.register(_capacity("constraint-1", current=5, limit=5))

        def _boom(schedule_id):
            raise AssertionError("fail-fast should have stopped before evaluating constraint-2")

        service.register(_predicate("constraint-2", _boom))
        service.assign("schedule-1", "constraint-1")
        service.assign("schedule-1", "constraint-2")

        result = service.evaluate("schedule-1")

        assert result.satisfied is False
        assert result.violations == ("constraint-1",)

    def test_enable_disable(self):
        service = ConstraintService()
        service.register(_capacity("constraint-1", current=5, limit=5))
        service.assign("schedule-1", "constraint-1")

        assert service.evaluate("schedule-1").satisfied is False

        disabled = service.disable("constraint-1")
        assert isinstance(disabled, Constraint)
        assert disabled.enabled is False
        assert service.evaluate("schedule-1").satisfied is True

        enabled = service.enable("constraint-1")
        assert enabled.enabled is True
        assert service.evaluate("schedule-1").satisfied is False

        with pytest.raises(Error):
            service.enable("unknown-constraint")

        with pytest.raises(Error):
            service.disable("   ")

    def test_invalid_constraint_rejection(self):
        with pytest.raises(Error):
            Constraint(constraint_id="   ", type="capacity", configuration={"current": 1, "limit": 5}, enabled=True)

        with pytest.raises(Error):
            Constraint(constraint_id="c1", type="unknown-type", configuration={}, enabled=True)

        with pytest.raises(Error):
            Constraint(constraint_id="c1", type="capacity", configuration={"current": 1}, enabled=True)

        with pytest.raises(Error):
            Constraint(
                constraint_id="c1", type="capacity", configuration={"current": -1, "limit": 5}, enabled=True
            )

        with pytest.raises(Error):
            Constraint(
                constraint_id="c1",
                type="maintenance",
                configuration={"start": _at(5), "end": _at(-5)},
                enabled=True,
            )

        with pytest.raises(Error):
            Constraint(constraint_id="c1", type="holiday", configuration={"dates": {date.today()}}, enabled=True)

        with pytest.raises(Error):
            Constraint(constraint_id="c1", type="predicate", configuration={"predicate": "not-callable"}, enabled=True)

        with pytest.raises(Error):
            Constraint(
                constraint_id="c1", type="capacity", configuration={"current": 1, "limit": 5}, enabled="yes"
            )

        service = ConstraintService()

        with pytest.raises(Error):
            service.register("not-a-constraint")

        with pytest.raises(Error):
            service.assign("   ", "constraint-1")

        with pytest.raises(Error):
            service.evaluate("   ")

        with pytest.raises(Error):
            service.enable("   ")
