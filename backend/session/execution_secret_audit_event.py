from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from uuid import uuid4

from .execution_secret_audit_error import (
    ExecutionSecretAuditError,
)

from .execution_secret_audit_operation import (
    ExecutionSecretAuditOperation,
)

_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "value",
        "raw_value",
        "secret_value",
        "plaintext",
        "plaintext_value",
    }
)


@dataclass(frozen=True)
class ExecutionSecretAuditEvent:
    """
    Immutable record of a single security-sensitive operation
    performed against a secret.

    The event is a value object only. It performs no recording of
    its own; appending and looking up events is the responsibility of
    an execution secret audit service. It never carries a raw secret
    value: metadata may describe an operation, but never the secret
    material itself.

    Attributes:
        event_id: The event's unique identifier
        secret_id: The identifier of the secret the operation was
            performed against
        session_id: The identifier of the execution session the
            operation was performed within
        principal: Who or what performed the operation
        operation: The category of operation performed, drawn from
            ExecutionSecretAuditOperation
        timestamp: When the operation occurred
        metadata: Arbitrary additional details about the operation,
            never including a raw secret value
    """

    secret_id: str

    session_id: str

    principal: str

    operation: ExecutionSecretAuditOperation

    event_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.event_id, "event ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.principal, "principal")

        try:
            normalized_operation = ExecutionSecretAuditOperation(self.operation)
        except ValueError as error:
            raise ExecutionSecretAuditError(
                f"Cannot build an execution secret audit event with an invalid operation: {error}"
            ) from error

        object.__setattr__(self, "operation", normalized_operation)

        if not isinstance(self.timestamp, datetime):
            raise ExecutionSecretAuditError(
                "Cannot build an execution secret audit event with a non-datetime timestamp."
            )

        if not isinstance(self.metadata, dict):
            raise ExecutionSecretAuditError(
                "Cannot build an execution secret audit event with a non-dict metadata."
            )

        forbidden_keys = _FORBIDDEN_METADATA_KEYS.intersection(self.metadata.keys())

        if forbidden_keys:
            raise ExecutionSecretAuditError(
                f"Cannot build an execution secret audit event with a raw secret value in metadata: "
                f"{sorted(forbidden_keys)}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAuditError(
                f"Cannot build an execution secret audit event with an empty or blank {field_name}."
            )
