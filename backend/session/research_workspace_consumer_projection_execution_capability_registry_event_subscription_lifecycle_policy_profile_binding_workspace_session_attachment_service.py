from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_attachment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_attachment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_attachment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentService:
    """
    Maintains a metadata-only registry of runtime artifacts —
    reports, logs, exports, and configs — produced during a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    downstream stages can discover them by reference without a large
    artifact payload ever being embedded in session state.

    The service's responsibility is registering and retrieving
    attachment metadata, not storing artifact payloads. It does NOT
    read, write, or move whatever an attachment's location points at;
    it relies on the existing execution session service, given at
    construction time, only to confirm a session ID is genuinely
    known before an attachment is registered against it.

    Behavior:
    - A session may hold multiple attachments; attach() never
      replaces or limits how many a session can have
    - list() returns a session's currently attached artifacts in the
      order they were attached
    - detach() removes an artifact from list()'s results, but never
      erases its record: get() and exists() keep answering for a
      detached attachment ID, preserving it for audit

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before an attachment is
                registered against it. Any object exposing
                `session(session_id)`, raising if the session is
                unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._attachments = {}
        self._attachment_ids_by_session_id = {}
        self._detached_attachment_ids = set()
        self._lock = RLock()

    def attach(
        self,
        session_id: str,
        attachment: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentResult:
        """
        Register a new attachment against a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError:
                If session_id is None or blank, attachment is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment
                belonging to session_id, the execution session
                service does not recognize session_id, or the
                attachment's ID is already registered
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(attachment, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                "Cannot attach an invalid session attachment: attachment must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment."
            )

        if attachment.session_id != session_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                f"Cannot attach an attachment for session ID {attachment.session_id!r} to session ID "
                f"{session_id!r}."
            )

        with self._lock:
            self._ensure_session_known(session_id)

            if attachment.attachment_id in self._attachments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                    f"Attachment ID {attachment.attachment_id!r} is already registered."
                )

            self._attachments[attachment.attachment_id] = attachment
            self._attachment_ids_by_session_id.setdefault(session_id, []).append(attachment.attachment_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentResult(
                attachment_id=attachment.attachment_id,
                attached=True,
            )

    def get(self, attachment_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment:
        """
        Look up an attachment's metadata, whether it is currently
        attached or has been detached.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError:
                If attachment_id is None or blank, or no attachment is
                registered under it
        """

        self._validate_id(attachment_id, "attachment ID")

        with self._lock:
            return self._resolve(attachment_id)

    def list(self, session_id: str) -> tuple:
        """
        List a session's currently attached artifacts, in the order
        they were attached. Detached attachments are excluded.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return tuple(
                self._attachments[attachment_id]
                for attachment_id in self._attachment_ids_by_session_id.get(session_id, [])
                if attachment_id not in self._detached_attachment_ids
            )

    def detach(self, attachment_id: str) -> None:
        """
        Detach an artifact, removing it from list()'s results while
        keeping its record queryable through get() and exists().

        Detaching an attachment that is already detached is not an
        error.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError:
                If attachment_id is None or blank, or no attachment is
                registered under it
        """

        self._validate_id(attachment_id, "attachment ID")

        with self._lock:
            self._resolve(attachment_id)

            self._detached_attachment_ids.add(attachment_id)

    def exists(self, attachment_id: str) -> bool:
        """
        Check whether an attachment ID is registered, whether it is
        currently attached or has been detached.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError:
                If attachment_id is None or blank
        """

        self._validate_id(attachment_id, "attachment ID")

        with self._lock:
            return attachment_id in self._attachments

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve(self, attachment_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment:
        attachment = self._attachments.get(attachment_id)

        if attachment is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                f"No session attachment is registered under attachment ID {attachment_id!r}."
            )

        return attachment

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError(
                f"Cannot operate with an empty or blank {label}."
            )
