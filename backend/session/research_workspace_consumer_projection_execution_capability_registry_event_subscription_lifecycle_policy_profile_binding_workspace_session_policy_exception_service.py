from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_exception_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_exception import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException,
    VALID_SESSION_POLICY_EXCEPTION_SCOPES,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_exception_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult,
)

_PENDING = "PENDING"
_APPROVED = "APPROVED"
_REVOKED = "REVOKED"


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionService:
    """
    Grants temporary, auditable overrides of a single, configured
    aspect of the session policy governing a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session, without ever
    modifying the base policy itself.

    The service's responsibility is the exception's own lifecycle,
    not the base policy. It does NOT read, assign, or alter a
    session's base policy; a caller is expected to call validate()
    immediately before evaluating a session against its base policy,
    and to honor an approved exception's override instead of the base
    policy's normal behavior when the result is approved.

    Behavior:
    - Every exception starts pending and must be explicitly
      approve()-ed before it is usable
    - An exception past its expires_at is treated as no longer
      usable, whether or not it was ever approved; expiration is
      checked lazily, at the moment it matters, rather than swept in
      the background
    - revoke() may be called on a pending or approved exception at any
      time, permanently ending its usability
    - Every exception ever requested remains in this service's
      history for as long as the service exists; nothing is ever
      deleted

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, scope: str, duration_seconds: float):
        """
        Args:
            scope: Which aspect of a base policy every exception this
                service grants overrides, one of "MAX_RUNTIME",
                "MAX_IDLE", or "ALLOW_RESTORE"
            duration_seconds: How long, in seconds, an exception
                remains usable after it is requested

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If scope is not one of VALID_SESSION_POLICY_EXCEPTION_SCOPES,
                or duration_seconds is not a positive number
        """

        if scope not in VALID_SESSION_POLICY_EXCEPTION_SCOPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                f"Invalid scope {scope!r}. Must be one of {VALID_SESSION_POLICY_EXCEPTION_SCOPES!r}."
            )

        if (
            duration_seconds is None
            or isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or duration_seconds <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                f"Invalid duration_seconds {duration_seconds!r}; duration_seconds must be a positive number of "
                "seconds."
            )

        self._scope = scope
        self._duration_seconds = duration_seconds
        self._exceptions_by_id = {}
        self._status_by_id = {}
        self._lock = RLock()

    def request(
        self, session_id: str, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException:
        """
        Request a new, pending exception for a session's base policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If session_id or policy_id is None or blank
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(policy_id, "policy ID")

        exception = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException(
            exception_id=str(uuid4()),
            session_id=session_id,
            policy_id=policy_id,
            scope=self._scope,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._duration_seconds),
        )

        with self._lock:
            self._exceptions_by_id[exception.exception_id] = exception
            self._status_by_id[exception.exception_id] = _PENDING

            return exception

    def approve(
        self, exception_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult:
        """
        Approve a pending exception, making it usable until it
        expires.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If exception_id is None or blank, no exception is
                registered under it, or it has already been approved
                or revoked
        """

        self._validate_id(exception_id, "exception ID")

        with self._lock:
            exception = self._resolve(exception_id)
            status = self._status_by_id[exception_id]

            if status != _PENDING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                    f"Cannot approve exception ID {exception_id!r}: it is already {status.lower()}."
                )

            if exception.expires_at <= datetime.now(timezone.utc):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult(
                    approved=False,
                    reason=f"exception ID {exception_id!r} expired before it could be approved.",
                )

            self._status_by_id[exception_id] = _APPROVED

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult(
                approved=True,
            )

    def revoke(
        self, exception_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult:
        """
        Permanently end a pending or approved exception's usability.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If exception_id is None or blank, or no exception is
                registered under it
        """

        self._validate_id(exception_id, "exception ID")

        with self._lock:
            self._resolve(exception_id)

            self._status_by_id[exception_id] = _REVOKED

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult(
                approved=False,
                reason=f"exception ID {exception_id!r} was revoked.",
            )

    def active(self, session_id: str) -> tuple:
        """
        List every currently approved, unexpired exception requested
        for a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            now = datetime.now(timezone.utc)

            return tuple(
                exception
                for exception in self._exceptions_by_id.values()
                if exception.session_id == session_id
                and self._status_by_id[exception.exception_id] == _APPROVED
                and exception.expires_at > now
            )

    def validate(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult:
        """
        Check whether a session currently has a usable exception,
        immediately before its base policy is evaluated.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            if self.active(session_id):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult(
                    approved=True,
                )

            latest = self._latest_for_session(session_id)

            if latest is None:
                reason = f"no policy exception has been requested for session ID {session_id!r}."
            elif self._status_by_id[latest.exception_id] == _REVOKED:
                reason = f"exception ID {latest.exception_id!r} was revoked."
            elif self._status_by_id[latest.exception_id] == _PENDING:
                reason = f"exception ID {latest.exception_id!r} is still pending approval."
            else:
                reason = f"exception ID {latest.exception_id!r} has expired."

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult(
                approved=False,
                reason=reason,
            )

    def _latest_for_session(
        self, session_id: str
    ):
        matching = [
            exception for exception in self._exceptions_by_id.values() if exception.session_id == session_id
        ]

        return matching[-1] if matching else None

    def _resolve(
        self, exception_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException:
        exception = self._exceptions_by_id.get(exception_id)

        if exception is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                f"No policy exception is registered under exception ID {exception_id!r}."
            )

        return exception

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                f"Cannot operate with an empty or blank {label}."
            )
