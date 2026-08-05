from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_label_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_label import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabel,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_label_index import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelIndex,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelService:
    """
    Attaches searchable key/value labels to consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution sessions, and maintains an
    index over them, so operational queries can find matching
    sessions without scanning every one.

    The service's responsibility is label storage and indexing, not
    execution. It does NOT interpret what a label means; it relies on
    the existing execution session service, given at construction
    time, only to confirm a session ID is genuinely known before a
    label is added to or removed from it.

    Behavior:
    - A session may carry multiple labels, one value per key
    - Every add() and remove() updates the key index in the same
      operation, so find() never sees stale results
    - find() matches a key and value exactly; no partial or prefix
      matching is performed
    - rebuild_index() recomputes the index from the labels currently
      stored, and returns its resulting state

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before a label is added to or
                removed from it. Any object exposing
                `session(session_id)`, raising if the session is
                unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._labels_by_session_id = {}
        self._session_ids_by_key = {}
        self._lock = RLock()

    def add(self, session_id: str, key: str, value: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabel:
        """
        Attach a new label to a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError:
                If session_id or key is None or blank, value is None,
                blank, or not a string, the execution session service
                does not recognize session_id, or the session already
                carries a label under key
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_session_known(session_id)

            existing = self._labels_by_session_id.get(session_id, {})

            if key in existing:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                    f"Session ID {session_id!r} already carries a label under key {key!r}. Remove it first to "
                    "change its value."
                )

            label = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabel(
                session_id=session_id,
                key=key,
                value=value,
            )

            self._labels_by_session_id.setdefault(session_id, {})[key] = label
            self._session_ids_by_key.setdefault(key, set()).add(session_id)

            return label

    def remove(self, session_id: str, key: str) -> None:
        """
        Remove a session's label by key, if it has one.

        Removing a key that was never added, or already removed, is
        not an error.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError:
                If session_id or key is None or blank, or the
                execution session service does not recognize
                session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_session_known(session_id)

            session_labels = self._labels_by_session_id.get(session_id)

            if session_labels is None or key not in session_labels:
                return

            del session_labels[key]

            indexed_session_ids = self._session_ids_by_key.get(key)

            if indexed_session_ids is not None:
                indexed_session_ids.discard(session_id)

    def labels(self, session_id: str) -> tuple:
        """
        List every label attached to a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return tuple(self._labels_by_session_id.get(session_id, {}).values())

    def find(self, key: str, value: str) -> tuple:
        """
        Find every session carrying an exact key/value label match.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError:
                If key or value is None or blank
        """

        self._validate_id(key, "key")
        self._validate_id(value, "value")

        with self._lock:
            candidate_session_ids = self._session_ids_by_key.get(key, set())

            return tuple(
                sorted(
                    session_id
                    for session_id in candidate_session_ids
                    if self._labels_by_session_id.get(session_id, {}).get(key) is not None
                    and self._labels_by_session_id[session_id][key].value == value
                )
            )

    def rebuild_index(self) -> tuple:
        """
        Recompute the label index from the labels currently stored.

        Returns:
            A ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelIndex
            for every key currently in use, ordered by key
        """

        with self._lock:
            rebuilt = {}

            for session_id, session_labels in self._labels_by_session_id.items():
                for key in session_labels:
                    rebuilt.setdefault(key, set()).add(session_id)

            self._session_ids_by_key = rebuilt

            return tuple(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelIndex(
                    label_key=key,
                    session_ids=tuple(sorted(session_ids)),
                )
                for key, session_ids in sorted(rebuilt.items())
            )

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                f"Cannot operate with an empty or blank {label}."
            )
