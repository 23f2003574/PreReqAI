from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_constraint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_constraint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_constraint_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


def _evaluate_equals(constraint_value, context) -> bool:
    return context.get(constraint_value["key"]) == constraint_value["value"]


def _evaluate_min(constraint_value, context) -> bool:
    key = constraint_value["key"]

    if key not in context:
        return False

    return context[key] >= constraint_value["value"]


def _evaluate_max(constraint_value, context) -> bool:
    key = constraint_value["key"]

    if key not in context:
        return False

    return context[key] <= constraint_value["value"]


def _evaluate_present(constraint_value, context) -> bool:
    return constraint_value["key"] in context


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintService:
    """
    Enforces constraints on consumer projection execution capability
    registry event subscription lifecycle policy profile bindings, so
    a binding is only considered valid when its predefined capability
    and runtime requirements are satisfied against a runtime context.

    The service's responsibility is constraint registration, removal,
    and evaluation, not binding creation, activation, or resolution.
    It does NOT create bindings, activate or deactivate bindings,
    mutate the binding registry, persist state externally, log, or
    publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two constraints may share a constraint ID
    - Order-preserving: Constraints are evaluated in the order they
      were registered
    - Exhaustive: Every registered constraint is evaluated; the first
      failure does not stop evaluation
    - Active-only: An inactive binding is never satisfied, regardless
      of its constraints
    """

    _EVALUATORS = {
        "equals": _evaluate_equals,
        "min": _evaluate_min,
        "max": _evaluate_max,
        "present": _evaluate_present,
    }

    def __init__(self, binding_registry, activation_service):
        """
        Args:
            binding_registry: The registry used to verify a binding
                exists. Any object exposing `find(binding_id)` is
                accepted
            activation_service: The service used to check whether a
                binding is active. Any object exposing
                `state(binding_id)` is accepted
        """

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot initialize constraint service with a None binding registry."
            )

        if activation_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot initialize constraint service with a None activation service."
            )

        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._constraints = {}
        self._constraint_order = []
        self._lock = RLock()

    def add_constraint(
        self,
        constraint: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
    ) -> None:
        """
        Register a new binding constraint.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError:
                If the constraint is None, is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
                its constraint ID is already registered, or no binding
                is registered under its binding ID
        """

        if constraint is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot add a None constraint."
            )

        if not isinstance(
            constraint,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot add a constraint: constraint must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraint."
            )

        self._resolve_binding(constraint.binding_id)

        with self._lock:
            if constraint.constraint_id in self._constraints:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                    f"Constraint ID {constraint.constraint_id!r} is already registered."
                )

            self._constraints[constraint.constraint_id] = constraint
            self._constraint_order.append(constraint.constraint_id)

    def remove_constraint(self, constraint_id: str) -> None:
        """
        Remove a registered binding constraint.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError:
                If the constraint ID is None or blank, or no
                constraint is registered under it
        """

        self._validate_identifier(constraint_id, "constraint ID")

        with self._lock:
            if constraint_id not in self._constraints:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                    f"Constraint ID {constraint_id!r} is not registered."
                )

            del self._constraints[constraint_id]
            self._constraint_order.remove(constraint_id)

    def evaluate(
        self,
        binding_id: str,
        context,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult:
        """
        Evaluate every constraint registered for a binding against a
        runtime context.

        An inactive binding is never satisfied and skips constraint
        evaluation entirely.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError:
                If the binding ID is None or blank, no binding is
                registered under it, or context is None
        """

        self._resolve_binding(binding_id)

        if context is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                "Cannot evaluate constraints against a None context."
            )

        if self._activation_service.state(binding_id) != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult(
                satisfied=False,
                failed_constraints=(),
            )

        failed = []

        for constraint in self.constraints(binding_id):
            evaluator = self._EVALUATORS[constraint.constraint_type]

            if not evaluator(constraint.constraint_value, context):
                failed.append(constraint)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintResult(
            satisfied=len(failed) == 0,
            failed_constraints=tuple(failed),
        )

    def constraints(self, binding_id: str) -> tuple:
        """
        List every constraint registered for a binding, in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            return tuple(
                self._constraints[constraint_id]
                for constraint_id in self._constraint_order
                if self._constraints[constraint_id].binding_id == binding_id
            )

    def _resolve_binding(self, binding_id: str):
        self._validate_identifier(binding_id, "binding ID")

        binding = self._binding_registry.find(binding_id)

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )

        return binding

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingConstraintError(
                f"Cannot operate with an empty or blank {label}."
            )
