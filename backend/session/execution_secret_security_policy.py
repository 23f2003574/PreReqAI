from dataclasses import (
    dataclass,
)

from .execution_secret_security_policy_error import (
    ExecutionSecretSecurityPolicyError,
)


@dataclass(frozen=True)
class ExecutionSecretSecurityPolicy:
    """
    Immutable declaration of which security controls are mandatory
    for a secret.

    The policy is a value object only. It performs no enforcement of
    its own; registering, validating against, and disabling security
    policies is the responsibility of an execution secret security
    policy service.

    Attributes:
        policy_id: The policy's unique identifier
        secret_id: The identifier of the secret this policy's
            requirements apply to
        require_rotation: Whether the secret must have a recorded
            rotation history
        require_lease: Whether the secret must currently have an
            active lease
        require_trust: Whether every principal with access to the
            secret must be trusted above LOW
        require_audit: Whether the secret must have a recorded audit
            history
        enabled: Whether this policy's requirements currently apply;
            a disabled policy is ignored entirely
    """

    policy_id: str

    secret_id: str

    require_rotation: bool = False

    require_lease: bool = False

    require_trust: bool = False

    require_audit: bool = False

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.secret_id, "secret ID")

        for field_name in (
            "require_rotation",
            "require_lease",
            "require_trust",
            "require_audit",
            "enabled",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ExecutionSecretSecurityPolicyError(
                    f"Cannot build an execution secret security policy with a non-bool {field_name}."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretSecurityPolicyError(
                f"Cannot build an execution secret security policy with an empty or blank {field_name}."
            )
