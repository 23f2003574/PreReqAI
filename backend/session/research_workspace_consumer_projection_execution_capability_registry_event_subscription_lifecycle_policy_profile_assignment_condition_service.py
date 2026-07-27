from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_condition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_condition_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_condition_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionService:
    """
    Manages and evaluates conditional profile assignments based on runtime context.

    This service resolves the effective profile dynamically using expressions evaluated against
    context attributes. If no conditions match, it falls back to the normal profile assignment.

    The service is:
    - Thread-safe: Mutex-guarded read and write operations
    - Priority-ordered: Evaluates registered conditions in descending priority order
    - Deterministic: Rejects duplicate priorities for the same target, guaranteeing unique evaluation order
    - Fallback-supported: Falls back to normal assignment if no conditional expressions match
    """

    def __init__(self, assignment_registry_service, profile_service):
        """
        Args:
            assignment_registry_service: Any object exposing find(target_id)
            profile_service: Any object exposing contains(profile_id)
        """
        if assignment_registry_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot initialize condition service with a None assignment registry service."
            )

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot initialize condition service with a None profile service."
            )

        self._assignment_registry_service = assignment_registry_service
        self._profile_service = profile_service
        self._conditions = {}  # condition_id -> condition
        self._condition_order = []
        self._lock = RLock()

    def register(
        self,
        condition: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition,
    ) -> None:
        """
        Registers a new profile assignment condition.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError:
                If condition is None, type mismatch, duplicate condition ID, referenced profile ID is unknown,
                or another condition has the same priority for the same target ID.
        """
        if condition is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot register a None condition."
            )

        if not isinstance(
            condition,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Must be a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition instance."
            )

        with self._lock:
            if condition.condition_id in self._conditions:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                    f"Condition ID {condition.condition_id!r} is already registered."
                )

            if not self._profile_service.contains(condition.profile_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                    f"Profile ID {condition.profile_id!r} is unknown/unregistered."
                )

            # Check duplicate priorities for the same target ID
            for cond in self._conditions.values():
                if cond.target_id == condition.target_id and cond.priority == condition.priority:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                        f"Duplicate priority {condition.priority} for target ID {condition.target_id!r} is not allowed."
                    )

            self._conditions[condition.condition_id] = condition
            self._condition_order.append(condition.condition_id)

    def remove(self, condition_id: str) -> None:
        """
        Removes the condition associated with condition_id.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError:
                If condition_id is None/blank or not registered.
        """
        self._validate_id(condition_id, "condition ID")

        with self._lock:
            if condition_id not in self._conditions:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                    f"Condition ID {condition_id!r} is not registered."
                )

            del self._conditions[condition_id]
            self._condition_order.remove(condition_id)

    def evaluate(
        self, target_id: str, context: dict
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult:
        """
        Evaluates registered conditions for target_id against the runtime context.
        First matching condition wins (descending priority order). Falls back to normal assignment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        eval_context = context if context is not None else {}

        with self._lock:
            target_conditions = [
                cond for cond in self._conditions.values() if cond.target_id == target_id
            ]

            if target_conditions:
                # Sort descending by priority
                target_conditions.sort(key=lambda x: x.priority, reverse=True)

                for cond in target_conditions:
                    if self._eval_expression(cond.expression, eval_context):
                        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult(
                            matched=True,
                            selected_profile_id=cond.profile_id,
                        )

            # Fallback to normal assignment
            normal_assignment = self._assignment_registry_service.find(target_id)
            if normal_assignment is not None:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult(
                    matched=False,
                    selected_profile_id=normal_assignment.profile_id,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult(
                matched=False,
                selected_profile_id=None,
            )

    def list(self, target_id: str) -> tuple:
        """
        Lists all conditions registered for target_id, preserving registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            result = []
            for cond_id in self._condition_order:
                cond = self._conditions[cond_id]
                if cond.target_id == target_id:
                    result.append(cond)
            return tuple(result)

    def _eval_expression(self, expression: str, context: dict) -> bool:
        try:
            # Safely evaluate context expression using eval with disabled builtins
            return bool(eval(expression, {"__builtins__": None}, context))
        except Exception:
            return False

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                f"Cannot perform condition operation with an empty or blank {label}."
            )
