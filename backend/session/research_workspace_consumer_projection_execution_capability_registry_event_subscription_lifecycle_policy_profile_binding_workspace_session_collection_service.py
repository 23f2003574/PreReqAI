from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_collection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_collection_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionService:
    """
    Organizes consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    sessions into named, reusable collections, so a caller can
    monitor or operate on a whole group at once instead of tracking
    each session's ID individually.

    The service's responsibility is grouping, not execution. It does
    NOT pause, cancel, or otherwise act on a collection's member
    sessions itself; it relies on the existing execution session
    service, given at construction time, only to confirm a session ID
    is genuinely known, and, when configured, to check whether it is
    still active.

    Behavior:
    - A session may belong to any number of collections at once
    - members() and collections() both preserve the order sessions
      were added in
    - add() rejects a session that is already a member; remove() of a
      non-member is not an error
    - When constructed with auto_remove_completed=True, members() and
      collections() silently evict any session the execution session
      service no longer reports as active as they encounter it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service, auto_remove_completed: bool = False):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known, and, when
                auto_remove_completed is True, to check whether it is
                still active. Any object exposing
                `session(session_id)`, raising if the session is
                unknown and otherwise returning an object with a
                `status` attribute, is accepted
            auto_remove_completed: When True, members() and
                collections() evict sessions that are no longer
                active as they're encountered
        """

        self._execution_session_service = execution_session_service
        self._auto_remove_completed = bool(auto_remove_completed)
        self._names_by_collection_id = {}
        self._session_ids_by_collection_id = {}
        self._collection_ids_by_session_id = {}
        self._lock = RLock()

    def create(self, name: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollection:
        """
        Create a new, empty collection.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If name is None or blank
        """

        self._validate_id(name, "name")

        with self._lock:
            collection_id = str(uuid4())

            self._names_by_collection_id[collection_id] = name
            self._session_ids_by_collection_id[collection_id] = []

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollection(
                collection_id=collection_id,
                name=name,
                session_ids=(),
            )

    def add(self, collection_id: str, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult:
        """
        Add a session to a collection.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If collection_id or session_id is None or blank, no
                collection is registered under collection_id, the
                execution session service does not recognize
                session_id, or the session is already a member
        """

        self._validate_id(collection_id, "collection ID")
        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)
            session_ids = self._resolve_members(collection_id)

            if session_id in session_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                    f"Session ID {session_id!r} is already a member of collection ID {collection_id!r}."
                )

            session_ids.append(session_id)
            self._collection_ids_by_session_id.setdefault(session_id, []).append(collection_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult(
                collection_id=collection_id,
                member_count=len(session_ids),
            )

    def remove(self, collection_id: str, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult:
        """
        Remove a session from a collection. Removing a session that
        is not a member is not an error.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If collection_id or session_id is None or blank, or
                no collection is registered under collection_id
        """

        self._validate_id(collection_id, "collection ID")
        self._validate_id(session_id, "session ID")

        with self._lock:
            session_ids = self._resolve_members(collection_id)

            self._evict(collection_id, session_id, session_ids)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult(
                collection_id=collection_id,
                member_count=len(session_ids),
            )

    def members(self, collection_id: str) -> tuple:
        """
        List a collection's member sessions, in the order they were
        added.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If collection_id is None or blank, or no collection is
                registered under it
        """

        self._validate_id(collection_id, "collection ID")

        with self._lock:
            session_ids = self._resolve_members(collection_id)

            if self._auto_remove_completed:
                for session_id in list(session_ids):
                    if not self._is_session_active(session_id):
                        self._evict(collection_id, session_id, session_ids)

            return tuple(session_ids)

    def collections(self, session_id: str) -> tuple:
        """
        List every collection a session currently belongs to, in the
        order it was added to each.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            collection_ids = self._collection_ids_by_session_id.get(session_id, [])

            if self._auto_remove_completed and not self._is_session_active(session_id):
                for collection_id in list(collection_ids):
                    self._evict(collection_id, session_id, self._session_ids_by_collection_id.get(collection_id, []))

                return ()

            return tuple(collection_ids)

    def delete(self, collection_id: str) -> None:
        """
        Delete a collection entirely.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError:
                If collection_id is None or blank, or no collection is
                registered under it
        """

        self._validate_id(collection_id, "collection ID")

        with self._lock:
            session_ids = self._resolve_members(collection_id)

            for session_id in tuple(session_ids):
                member_collection_ids = self._collection_ids_by_session_id.get(session_id)

                if member_collection_ids is not None and collection_id in member_collection_ids:
                    member_collection_ids.remove(collection_id)

            del self._session_ids_by_collection_id[collection_id]
            del self._names_by_collection_id[collection_id]

    def _evict(self, collection_id: str, session_id: str, session_ids: list) -> None:
        if session_id in session_ids:
            session_ids.remove(session_id)

        member_collection_ids = self._collection_ids_by_session_id.get(session_id)

        if member_collection_ids is not None and collection_id in member_collection_ids:
            member_collection_ids.remove(collection_id)

    def _is_session_active(self, session_id: str) -> bool:
        try:
            session = self._execution_session_service.session(session_id)
        except Exception:
            return False

        return session.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve_members(self, collection_id: str) -> list:
        session_ids = self._session_ids_by_collection_id.get(collection_id)

        if session_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                f"No session collection is registered under collection ID {collection_id!r}."
            )

        return session_ids

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError(
                f"Cannot operate with an empty or blank {label}."
            )
