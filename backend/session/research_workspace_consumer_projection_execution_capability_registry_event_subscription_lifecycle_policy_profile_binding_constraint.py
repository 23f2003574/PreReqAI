from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_constraint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError,
)

RECOGNIZED_CONSTRAINT_TYPES = (
    "equals",
    "min",
    "max",
    "present",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint:
    """
    Immutable requirement a consumer projection execution capability
    registry event subscription lifecycle policy profile binding must
    satisfy against a runtime context before it is considered valid.

    The constraint is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a binding constraint service.

    Attributes:
        constraint_id: The constraint's unique identifier
        binding_id: The identifier of the binding this constraint
            applies to
        constraint_type: The kind of check to perform; one of
            "equals", "min", "max", or "present"
        constraint_value: A mapping carrying "key" (the runtime
            context key to inspect) and, for "equals", "min", and
            "max", "value" (the expected or bounding value)
    """

    constraint_id: str

    binding_id: str

    constraint_type: str

    constraint_value: Mapping[str, object]

    def __post_init__(self):
        if self.constraint_id is None or not self.constraint_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot build a constraint with an empty or blank constraint ID."
            )

        if self.binding_id is None or not self.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot build a constraint with an empty or blank binding ID."
            )

        if self.constraint_type not in RECOGNIZED_CONSTRAINT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                f"Invalid constraint type {self.constraint_type!r}. Must be one of {RECOGNIZED_CONSTRAINT_TYPES}."
            )

        if not isinstance(self.constraint_value, Mapping) or not self.constraint_value.get("key"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot build a constraint whose constraint_value does not carry a non-blank 'key'."
            )

        if self.constraint_type in ("equals", "min", "max") and "value" not in self.constraint_value:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                f"Cannot build a {self.constraint_type!r} constraint whose constraint_value does not carry a 'value'."
            )
