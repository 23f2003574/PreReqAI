from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_condition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition,
    evaluate_condition_expression,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateService:
    """
    Evaluates consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    pipeline conditions and gates, blocking a stage from running
    until every registered condition and its gate, if any, are
    satisfied.

    The service's responsibility is registration, evaluation, and
    gate transition, not running a stage or a pipeline itself. It
    does NOT execute stages or pipelines; it reports whether a stage
    may proceed, leaving whoever runs the pipeline (for example, a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace
    execution pipeline service) to pause, fail, or advance based on
    that answer.

    Behavior:
    - A stage with no registered conditions and no registered gate is
      always clear to proceed
    - Every registered condition for a stage is evaluated before its
      gate; a condition whose expression evaluates false is handled
      according to its failure_action
    - A stage's gate blocks the stage while PENDING or CLOSED, and
      clears it while OPEN or BYPASSED
    - An automatic gate opens itself, and is recorded as OPEN, the
      first time its stage is evaluated while the gate is PENDING; a
      manual gate only opens or closes on an explicit open() or
      close() call
    - A stage may have at most one gate

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._conditions_by_id = {}
        self._conditions_by_stage = {}
        self._gates_by_id = {}
        self._gate_id_by_stage = {}
        self._pipeline_id_by_gate = {}
        self._gate_ids_by_pipeline = {}
        self._lock = RLock()

    def register_condition(
        self,
        condition: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition:
        """
        Register a condition to be evaluated before its stage runs.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If condition is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition, or its
                condition ID is already registered
        """

        if condition is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot register a None pipeline condition."
            )

        if not isinstance(condition, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot register a pipeline condition: condition must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition."
            )

        with self._lock:
            if condition.condition_id in self._conditions_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Condition ID {condition.condition_id!r} is already registered."
                )

            self._conditions_by_id[condition.condition_id] = condition
            self._conditions_by_stage.setdefault(condition.stage_id, []).append(condition)

            return condition

    def register_gate(
        self,
        gate: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate,
        pipeline_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
        """
        Register a gate guarding a stage, associated with the
        pipeline the stage belongs to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If gate is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate, pipeline_id is None
                or blank, the gate ID is already registered, or the
                gate's stage already has a registered gate
        """

        if gate is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot register a None pipeline gate."
            )

        if not isinstance(gate, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot register a pipeline gate: gate must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate."
            )

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            if gate.gate_id in self._gates_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Gate ID {gate.gate_id!r} is already registered."
                )

            if gate.stage_id in self._gate_id_by_stage:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Cannot register gate ID {gate.gate_id!r}: stage ID {gate.stage_id!r} already has a "
                    "registered gate."
                )

            self._gates_by_id[gate.gate_id] = gate
            self._gate_id_by_stage[gate.stage_id] = gate.gate_id
            self._pipeline_id_by_gate[gate.gate_id] = pipeline_id
            self._gate_ids_by_pipeline.setdefault(pipeline_id, []).append(gate.gate_id)

            return gate

    def evaluate(self, stage_id: str, context=None) -> bool:
        """
        Evaluate a stage's registered conditions and gate.

        Returns:
            True if the stage's conditions and gate all allow it to
            proceed, False if a condition configured to block or the
            stage's gate withholds it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If stage_id is None or blank, or a condition
                configured to fail the pipeline evaluates false
        """

        self._validate_id(stage_id, "stage ID")

        context = context if context is not None else {}

        with self._lock:
            conditions_clear = self._evaluate_conditions(stage_id, context)
            gate_clear = self._evaluate_gate(stage_id)

            return conditions_clear and gate_clear

    def open(self, gate_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
        """
        Manually open a pending gate.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If gate_id is None or blank, no gate is registered
                under it, or the gate is not pending
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            gate = self._resolve_gate(gate_id)

            if gate.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.PENDING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Cannot open gate ID {gate_id!r}: gate is {gate.status.value}, not pending."
                )

            opened = replace(gate, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.OPEN)
            self._gates_by_id[gate_id] = opened

            return opened

    def close(self, gate_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
        """
        Manually close a pending gate.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If gate_id is None or blank, no gate is registered
                under it, or the gate is not pending
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            gate = self._resolve_gate(gate_id)

            if gate.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.PENDING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Cannot close gate ID {gate_id!r}: gate is {gate.status.value}, not pending."
                )

            closed = replace(gate, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.CLOSED)
            self._gates_by_id[gate_id] = closed

            return closed

    def bypass(self, gate_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
        """
        Force a pending, non-mandatory gate open without a decision.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If gate_id is None or blank, no gate is registered
                under it, the gate is mandatory, or the gate is not
                pending
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            gate = self._resolve_gate(gate_id)

            if gate.mandatory:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Cannot bypass gate ID {gate_id!r}: gate is mandatory."
                )

            if gate.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.PENDING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Cannot bypass gate ID {gate_id!r}: gate is {gate.status.value}, not pending."
                )

            bypassed = replace(gate, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.BYPASSED)
            self._gates_by_id[gate_id] = bypassed

            return bypassed

    def pending(self, pipeline_id: str) -> tuple:
        """
        List every still-pending gate registered for a pipeline.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError:
                If pipeline_id is None or blank
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            gate_ids = self._gate_ids_by_pipeline.get(pipeline_id, ())

            return tuple(
                self._gates_by_id[gate_id]
                for gate_id in gate_ids
                if self._gates_by_id[gate_id].status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.PENDING
            )

    def _evaluate_conditions(self, stage_id: str, context) -> bool:
        proceed = True

        for condition in self._conditions_by_stage.get(stage_id, ()):
            satisfied = evaluate_condition_expression(condition.expression, context, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError)

            if satisfied:
                continue

            if condition.failure_action == "fail":
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                    f"Condition ID {condition.condition_id!r} failed for stage ID {stage_id!r}: "
                    f"{condition.expression!r} evaluated false."
                )

            if condition.failure_action == "block":
                proceed = False

        return proceed

    def _evaluate_gate(self, stage_id: str) -> bool:
        gate_id = self._gate_id_by_stage.get(stage_id)

        if gate_id is None:
            return True

        gate = self._gates_by_id[gate_id]

        if gate.status in (ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.OPEN, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.BYPASSED):
            return True

        if gate.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.CLOSED:
            return False

        if gate.gate_type == "automatic":
            opened = replace(gate, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.OPEN)
            self._gates_by_id[gate_id] = opened

            return True

        return False

    def _resolve_gate(self, gate_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
        gate = self._gates_by_id.get(gate_id)

        if gate is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                f"No gate is registered under gate ID {gate_id!r}."
            )

        return gate

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                f"Cannot operate with an empty or blank {label}."
            )
