from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationService:
    """
    Reserves logical workspace resources on behalf of a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    two conflicting sessions can never hold the same resource at the
    same time.

    The service's responsibility is exclusivity and expiry of
    reservations, not the resources themselves. It does NOT allocate,
    provision, or otherwise touch whatever a resource_type/resource_id
    pair refers to; it relies on the existing execution session
    service, given at construction time, only to confirm a session ID
    is genuinely known before a reservation is made on its behalf.

    Behavior:
    - At most one active reservation may exist for a given
      (resource_type, resource_id) pair at a time
    - A reservation past its expires_at is treated as no longer
      active: reserve() and owner() both disregard it, and cleanup()
      removes it from storage entirely
    - A session may hold multiple reservations at once, across
      different resources
    - release() frees a single reservation immediately; a caller
      finishing a session is expected to release() each of its
      reservations, found via reservations(session_id)

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before a reservation is made on
                its behalf. Any object exposing `session(session_id)`,
                raising if the session is unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._reservations = {}
        self._reservation_id_by_resource = {}
        self._reservation_ids_by_session_id = {}
        self._lock = RLock()

    def reserve(
        self,
        session_id: str,
        resource: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationResult:
        """
        Reserve a resource on behalf of a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError:
                If session_id is None or blank, resource is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation
                belonging to session_id, resource.expires_at is not in
                the future, the execution session service does not
                recognize session_id, the resource is already
                actively reserved, or the reservation ID is already
                registered
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(resource, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot reserve an invalid resource: resource must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation."
            )

        if resource.session_id != session_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                f"Cannot reserve a resource for session ID {resource.session_id!r} on behalf of session ID "
                f"{session_id!r}."
            )

        if resource.expires_at <= datetime.now(timezone.utc):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                f"Cannot reserve resource type {resource.resource_type!r} / resource ID "
                f"{resource.resource_id!r}: expires_at {resource.expires_at.isoformat()} is not in the future."
            )

        with self._lock:
            self._ensure_session_known(session_id)

            resource_key = (resource.resource_type, resource.resource_id)
            existing_reservation_id = self._reservation_id_by_resource.get(resource_key)

            if existing_reservation_id is not None:
                if self._is_active(self._reservations[existing_reservation_id]):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                        f"Resource type {resource.resource_type!r} / resource ID {resource.resource_id!r} is "
                        "already reserved."
                    )

                self._forget(existing_reservation_id)

            if resource.reservation_id in self._reservations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                    f"Reservation ID {resource.reservation_id!r} is already registered."
                )

            self._reservations[resource.reservation_id] = resource
            self._reservation_id_by_resource[resource_key] = resource.reservation_id
            self._reservation_ids_by_session_id.setdefault(session_id, []).append(resource.reservation_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationResult(
                reservation_id=resource.reservation_id,
                acquired=True,
            )

    def release(self, reservation_id: str) -> None:
        """
        Release a reservation, freeing its resource immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError:
                If reservation_id is None or blank, or no reservation
                is registered under it
        """

        self._validate_id(reservation_id, "reservation ID")

        with self._lock:
            self._resolve(reservation_id)

            self._forget(reservation_id)

    def reservations(self, session_id: str) -> tuple:
        """
        List a session's currently active reservations.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return tuple(
                self._reservations[reservation_id]
                for reservation_id in self._reservation_ids_by_session_id.get(session_id, [])
                if reservation_id in self._reservations and self._is_active(self._reservations[reservation_id])
            )

    def owner(self, resource_type: str, resource_id: str):
        """
        Look up the reservation currently holding a resource, if any.

        Returns:
            The resource's active ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation,
            or None if the resource is unreserved or its reservation
            has expired

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError:
                If resource_type or resource_id is None or blank
        """

        self._validate_id(resource_type, "resource type")
        self._validate_id(resource_id, "resource ID")

        with self._lock:
            reservation_id = self._reservation_id_by_resource.get((resource_type, resource_id))

            if reservation_id is None:
                return None

            reservation = self._reservations[reservation_id]

            if not self._is_active(reservation):
                return None

            return reservation

    def cleanup(self) -> tuple:
        """
        Remove every reservation past its expires_at from storage,
        freeing its resource.

        Returns:
            The reservations that were removed
        """

        with self._lock:
            expired = tuple(
                reservation for reservation in self._reservations.values() if not self._is_active(reservation)
            )

            for reservation in expired:
                self._forget(reservation.reservation_id)

            return expired

    def _is_active(self, reservation: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation) -> bool:
        return reservation.expires_at > datetime.now(timezone.utc)

    def _forget(self, reservation_id: str) -> None:
        reservation = self._reservations.pop(reservation_id, None)

        if reservation is None:
            return

        resource_key = (reservation.resource_type, reservation.resource_id)

        if self._reservation_id_by_resource.get(resource_key) == reservation_id:
            del self._reservation_id_by_resource[resource_key]

        session_reservation_ids = self._reservation_ids_by_session_id.get(reservation.session_id)

        if session_reservation_ids is not None and reservation_id in session_reservation_ids:
            session_reservation_ids.remove(reservation_id)

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve(self, reservation_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation:
        reservation = self._reservations.get(reservation_id)

        if reservation is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                f"No session reservation is registered under reservation ID {reservation_id!r}."
            )

        return reservation

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                f"Cannot operate with an empty or blank {label}."
            )
