from dataclasses import (
    dataclass,
)

from .execution_secret_access_error import (
    ExecutionSecretAccessError,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)


@dataclass(frozen=True)
class ExecutionSecretPolicy:
    """
    Immutable grant of access to a single secret, permitting one
    principal to perform a specific set of operations against it
    while the grant remains enabled.

    The policy is a value object only. It performs no authorization
    of its own; granting, revoking, and checking policies is the
    responsibility of an execution secret access service.

    Attributes:
        policy_id: The policy's unique identifier
        secret_id: The identifier of the secret this policy grants
            access to
        principal: Who or what this policy grants access to, e.g. an
            execution component's identifier
        operations: The non-empty set of operations this policy
            permits, drawn from ExecutionSecretOperation
        enabled: Whether this policy currently grants access; a
            disabled policy never authorizes anything
    """

    policy_id: str

    secret_id: str

    principal: str

    operations: frozenset

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.principal, "principal")

        if not isinstance(self.enabled, bool):
            raise ExecutionSecretAccessError(
                "Cannot build an execution secret policy with a non-bool enabled."
            )

        if self.operations is None:
            raise ExecutionSecretAccessError(
                "Cannot build an execution secret policy with an empty operations."
            )

        operations_list = list(self.operations)

        if not operations_list:
            raise ExecutionSecretAccessError(
                "Cannot build an execution secret policy with an empty operations."
            )

        try:
            normalized_operations = frozenset(
                ExecutionSecretOperation(operation) for operation in operations_list
            )
        except ValueError as error:
            raise ExecutionSecretAccessError(
                f"Cannot build an execution secret policy with an invalid operation: {error}"
            ) from error

        object.__setattr__(self, "operations", normalized_operations)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAccessError(
                f"Cannot build an execution secret policy with an empty or blank {field_name}."
            )
