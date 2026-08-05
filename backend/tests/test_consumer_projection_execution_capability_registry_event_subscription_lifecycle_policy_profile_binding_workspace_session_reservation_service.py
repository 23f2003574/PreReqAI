import time

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation as Reservation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationService as ReservationService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    reservation_service = ReservationService(session_service)
    return pipeline_service, session_service, reservation_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    return session_service.start(pipeline_id, owner=owner)


def _soon(seconds=5):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _reservation(reservation_id, session_id, resource_type="gpu", resource_id="gpu-1", expires_at=None):
    return Reservation(
        reservation_id=reservation_id,
        session_id=session_id,
        resource_type=resource_type,
        resource_id=resource_id,
        expires_at=expires_at if expires_at is not None else _soon(),
    )


class TestWorkspaceSessionReservationService:
    def test_reserve_resource(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        result = reservation_service.reserve(session.session_id, _reservation("reservation-1", session.session_id))

        assert isinstance(result, Result)
        assert result.reservation_id == "reservation-1"
        assert result.acquired is True

    def test_duplicate_reservation_rejection(self):
        pipeline_service, session_service, reservation_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        reservation_service.reserve(session_one.session_id, _reservation("reservation-1", session_one.session_id))

        with pytest.raises(Error):
            reservation_service.reserve(
                session_two.session_id, _reservation("reservation-2", session_two.session_id)
            )

    def test_release_reservation(self):
        pipeline_service, session_service, reservation_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        reservation_service.reserve(session_one.session_id, _reservation("reservation-1", session_one.session_id))
        reservation_service.release("reservation-1")

        # freed immediately: a different session can now reserve it
        result = reservation_service.reserve(
            session_two.session_id, _reservation("reservation-2", session_two.session_id)
        )
        assert result.acquired is True

        with pytest.raises(Error):
            reservation_service.release("reservation-1")

    def test_lookup_reservation_owner(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        assert reservation_service.owner("gpu", "gpu-1") is None

        reservation_service.reserve(session.session_id, _reservation("reservation-1", session.session_id))

        owner = reservation_service.owner("gpu", "gpu-1")
        assert isinstance(owner, Reservation)
        assert owner.reservation_id == "reservation-1"
        assert owner.session_id == session.session_id

    def test_cleanup_expired_reservations(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        reservation_service.reserve(
            session.session_id, _reservation("reservation-1", session.session_id, expires_at=_soon(0.05))
        )

        time.sleep(0.1)

        assert reservation_service.owner("gpu", "gpu-1") is None

        expired = reservation_service.cleanup()

        assert [reservation.reservation_id for reservation in expired] == ["reservation-1"]
        assert reservation_service.reservations(session.session_id) == ()

        with pytest.raises(Error):
            reservation_service.release("reservation-1")

    def test_session_reservation_listing(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        reservation_service.reserve(
            session.session_id, _reservation("reservation-1", session.session_id, resource_id="gpu-1")
        )
        reservation_service.reserve(
            session.session_id, _reservation("reservation-2", session.session_id, resource_id="gpu-2")
        )

        listed = reservation_service.reservations(session.session_id)

        assert {reservation.reservation_id for reservation in listed} == {"reservation-1", "reservation-2"}

        reservation_service.release("reservation-1")

        listed = reservation_service.reservations(session.session_id)
        assert [reservation.reservation_id for reservation in listed] == ["reservation-2"]

    def test_invalid_expiration_rejection(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        past = datetime.now(timezone.utc) - timedelta(seconds=5)

        with pytest.raises(Error):
            reservation_service.reserve(
                session.session_id, _reservation("reservation-1", session.session_id, expires_at=past)
            )

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, reservation_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            reservation_service.reserve("   ", _reservation("reservation-1", session.session_id))

        with pytest.raises(Error):
            reservation_service.reserve("unknown-session", _reservation("reservation-1", "unknown-session"))

        with pytest.raises(Error):
            reservation_service.reserve(session.session_id, _reservation("reservation-1", "different-session"))

        with pytest.raises(Error):
            reservation_service.reserve(session.session_id, "not-a-reservation")

        with pytest.raises(Error):
            reservation_service.release("   ")

        with pytest.raises(Error):
            reservation_service.release("unknown-reservation")

        with pytest.raises(Error):
            reservation_service.reservations("unknown-session")

        with pytest.raises(Error):
            reservation_service.owner("   ", "gpu-1")

        with pytest.raises(Error):
            reservation_service.owner("gpu", "   ")
