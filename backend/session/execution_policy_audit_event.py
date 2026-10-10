from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from typing import (
    Mapping,
)

from .execution_policy_audit_error import (
    ExecutionPolicyAuditError,
)

EVENT_TYPE_EVALUATION = "evaluation"

EVENT_TYPE_CONFLICT = "conflict"

EVENT_TYPE_EXCEPTION = "exception"

EVENT_TYPE_SIMULATION = "simulation"

EVENT_TYPE_ENFORCEMENT = "enforcement"

EVENT_TYPES = (
    EVENT_TYPE_EVALUATION,
    EVENT_TYPE_CONFLICT,
    EVENT_TYPE_EXCEPTION,
    EVENT_TYPE_SIMULATION,
    EVENT_TYPE_ENFORCEMENT,
)

SENSITIVE_METADATA_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "value_ref",
    "runtime_value",
)


@dataclass(frozen=True)
class ExecutionPolicyAuditEvent:
    """
    Immutable record of a single policy evaluation, conflict,
    exception, simulation, or enforcement decision.

    The event is a value object only. It performs no recording of
    its own; appending, listing, and purging events is the
    responsibility of an execution policy audit service.

    metadata may never carry a secret or runtime value: any key
    whose name suggests one, e.g. containing "secret", "token", or
    "credential", is rejected outright rather than silently dropped,
    so a caller discovers the mistake at the point it happens.

    Attributes:
        event_id: The event's unique identifier
        session_id: The identifier of the execution session this
            event concerns
        policy_ids: The identifiers of the policies this event
            concerns, possibly empty
        event_type: One of EVENT_TYPES
        decision: The outcome this event records, e.g. "allowed",
            "denied", "detected", or "resolved"
        timestamp: When the underlying event occurred
        metadata: Additional non-sensitive context about the event
    """

    event_id: str

    session_id: str

    policy_ids: tuple

    event_type: str

    decision: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    metadata: Mapping = field(
        default_factory=lambda: MappingProxyType({}),
    )

    def __post_init__(self):
        self._require_text(self.event_id, "event ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.decision, "decision")

        if self.policy_ids is None:
            raise ExecutionPolicyAuditError(
                "Cannot build an execution policy audit event with a None policy_ids."
            )

        policy_ids_list = list(self.policy_ids)

        for policy_id in policy_ids_list:
            if not isinstance(policy_id, str) or not policy_id.strip():
                raise ExecutionPolicyAuditError(
                    "Cannot build an execution policy audit event with a blank policy ID."
                )

        object.__setattr__(self, "policy_ids", tuple(policy_ids_list))

        if self.event_type not in EVENT_TYPES:
            raise ExecutionPolicyAuditError(
                f"Cannot build an execution policy audit event with an unknown event_type: {self.event_type!r}."
            )

        if not isinstance(self.timestamp, datetime):
            raise ExecutionPolicyAuditError(
                "Cannot build an execution policy audit event with a non-datetime timestamp."
            )

        if self.metadata is None:
            raise ExecutionPolicyAuditError(
                "Cannot build an execution policy audit event with a None metadata."
            )

        for key in self.metadata:
            if not isinstance(key, str):
                raise ExecutionPolicyAuditError(
                    "Cannot build an execution policy audit event with a non-string metadata key."
                )

            lowered = key.lower()

            if any(marker in lowered for marker in SENSITIVE_METADATA_KEY_MARKERS):
                raise ExecutionPolicyAuditError(
                    f"Cannot build an execution policy audit event with a sensitive metadata key: {key!r}."
                )

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyAuditError(
                f"Cannot build an execution policy audit event with an empty or blank {field_name}."
            )
