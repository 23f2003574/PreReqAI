from dataclasses import (
    dataclass,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

from .execution_secret_trust_error import (
    ExecutionSecretTrustError,
)

from .execution_secret_trust_level import (
    ExecutionSecretTrustLevel,
)


@dataclass(frozen=True)
class ExecutionSecretTrustPolicy:
    """
    Immutable declaration of a principal's trust level, and the
    operations that trust level explicitly grants beyond whatever
    lower-risk operations it inherits.

    The policy is a value object only. It performs no authorization
    of its own; registering, disabling, and checking trust policies
    is the responsibility of an execution secret trust service.

    Attributes:
        policy_id: The policy's unique identifier
        principal: Who or what this policy declares a trust level for
        trust_level: How much this principal is trusted, drawn from
            ExecutionSecretTrustLevel
        allowed_operations: The operations this policy explicitly
            grants, on top of whatever trust_level inherits on its
            own. May be empty
        enabled: Whether this policy currently applies; a disabled
            policy never grants or contributes to trust
    """

    policy_id: str

    principal: str

    trust_level: ExecutionSecretTrustLevel

    allowed_operations: frozenset

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.principal, "principal")

        try:
            normalized_trust_level = ExecutionSecretTrustLevel(self.trust_level)
        except ValueError as error:
            raise ExecutionSecretTrustError(
                f"Cannot build an execution secret trust policy with an invalid trust_level: {error}"
            ) from error

        object.__setattr__(self, "trust_level", normalized_trust_level)

        if not isinstance(self.enabled, bool):
            raise ExecutionSecretTrustError(
                "Cannot build an execution secret trust policy with a non-bool enabled."
            )

        if self.allowed_operations is None:
            raise ExecutionSecretTrustError(
                "Cannot build an execution secret trust policy with a None allowed_operations."
            )

        try:
            normalized_operations = frozenset(
                ExecutionSecretOperation(operation) for operation in self.allowed_operations
            )
        except ValueError as error:
            raise ExecutionSecretTrustError(
                f"Cannot build an execution secret trust policy with an invalid operation: {error}"
            ) from error

        object.__setattr__(self, "allowed_operations", normalized_operations)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretTrustError(
                f"Cannot build an execution secret trust policy with an empty or blank {field_name}."
            )
