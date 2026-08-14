from dataclasses import (
    dataclass,
)

from typing import Optional

from .execution_policy_conflict_error import (
    ExecutionPolicyConflictError,
)

STATUS_UNRESOLVED = "unresolved"

STATUS_RESOLVED = "resolved"

STATUSES = (
    STATUS_UNRESOLVED,
    STATUS_RESOLVED,
)


@dataclass(frozen=True)
class ExecutionPolicyConflict:
    """
    Immutable record of a single contradictory rule found between
    two or more policies, and how it was resolved, if at all.

    The conflict is a value object only. It performs no detection or
    resolution of its own; finding contradictions, recording an
    explicit resolution, and tracking which conflicts remain
    unresolved is the responsibility of an execution policy conflict
    service.

    Attributes:
        conflict_id: The conflict's unique identifier
        policy_ids: The identifiers of the policies whose rules
            contradict each other, at least two, all distinct
        rule: The rule that one policy asserts and another negates
        resolution: How this conflict was resolved, or None while it
            remains unresolved
        status: STATUS_UNRESOLVED or STATUS_RESOLVED. Must be
            STATUS_RESOLVED if and only if resolution is set
    """

    conflict_id: str

    policy_ids: tuple

    rule: str

    resolution: Optional[str] = None

    status: str = STATUS_UNRESOLVED

    def __post_init__(self):
        self._require_text(self.conflict_id, "conflict ID")
        self._require_text(self.rule, "rule")

        if self.policy_ids is None:
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict with a None policy_ids."
            )

        policy_ids_list = list(self.policy_ids)

        if len(policy_ids_list) < 2:
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict with fewer than two policy_ids."
            )

        for policy_id in policy_ids_list:
            if not isinstance(policy_id, str) or not policy_id.strip():
                raise ExecutionPolicyConflictError(
                    "Cannot build an execution policy conflict with a blank policy ID."
                )

        if len(set(policy_ids_list)) != len(policy_ids_list):
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict with duplicate policy_ids."
            )

        object.__setattr__(self, "policy_ids", tuple(policy_ids_list))

        if self.resolution is not None and (not isinstance(self.resolution, str) or not self.resolution.strip()):
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict with a blank resolution."
            )

        if self.status not in STATUSES:
            raise ExecutionPolicyConflictError(
                f"Cannot build an execution policy conflict with an unknown status: {self.status!r}."
            )

        if self.status == STATUS_RESOLVED and self.resolution is None:
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict that is resolved but has no resolution."
            )

        if self.status == STATUS_UNRESOLVED and self.resolution is not None:
            raise ExecutionPolicyConflictError(
                "Cannot build an execution policy conflict that is unresolved but has a resolution."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyConflictError(
                f"Cannot build an execution policy conflict with an empty or blank {field_name}."
            )
