from backend.agent_capability_compatibility import LLMAgentCapabilityCompatibility
from backend.agent_capability_dependencies import LLMAgentCapabilityDependencyService
from backend.agent_capability_execution_control import ExecutionControlResult, LLMAgentCapabilityExecutionControl
from backend.agent_capability_execution_lifecycle import (
    CapabilityExecutionResult,
    LLMAgentCapabilityExecutionLifecycleService,
)
from backend.agent_capability_registry import LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import LLMAgentCapabilityResolver
from backend.agent_capability_selection import LLMAgentCapabilitySelector

from .models import CapabilityPreparationResult

ACTION_CANCEL = "cancel"
ACTION_CHECK_TIMEOUT = "check_timeout"
CONTROL_ACTIONS = frozenset({ACTION_CANCEL, ACTION_CHECK_TIMEOUT})


class InvalidCapabilityOrchestrationError(ValueError):
    """Raised when control() is given an action other than "cancel" or
    "check_timeout"."""


class LLMAgentCapabilityOrchestrator:
    """The final composition root for the whole Agent Capability
    subsystem: coordinates Commits #1-#12's own already-shipped services
    through prepare -> select -> execute -> control, without
    reimplementing a single one of them.

    Every actual decision is delegated to a real collaborator this
    subsystem already ships -- Commit #2's own LLMAgentCapabilityResolver,
    Commit #4's own LLMAgentCapabilityDependencyService, Commit #5's own
    LLMAgentCapabilityCompatibility, Commit #6's own
    LLMAgentCapabilitySelector, Commit #10's own
    LLMAgentCapabilityExecutionLifecycleService (itself already composing
    Commits #1/#7/#8/#9), and Commit #12's own
    LLMAgentCapabilityExecutionControl (itself already composing Commit
    #7) -- each called exactly the way its own commit already
    established, never a second time with different (looser) rules.
    This class's only real work is sequencing those calls and reshaping
    their already-real results into one CapabilityPreparationResult (for
    prepare()) or simply forwarding a real collaborator's own result
    type unchanged (execute_selected(), control()); there is no
    resolution, dependency-graph, compatibility, scoring, validation,
    policy, or execution logic anywhere in this file that one of those
    six collaborators does not already own.

    "Failed preparation must prevent execution" holds by construction in
    prepare(), which never itself invokes anything: a capability that
    fails dependency or compatibility checks is simply left out of
    eligible_candidates and therefore out of selected_capabilities too
    -- it never reaches Commit #6's own select(). None of these are
    exceptions to catch -- LLMAgentCapabilityDependencyService.
    validate_dependencies() and LLMAgentCapabilityCompatibility.check()
    never raise for a broken/incompatible capability, they report it as
    data (valid/compatible), so there is nothing to swallow at either
    step; genuine exceptions (InvalidCapabilityResolutionError,
    InvalidCapabilitySelectionError, UnknownCapabilityExecutionError,
    ...) are never caught here and always propagate unchanged.
    execute_selected() enforces the same property independently and for
    free: it delegates straight to Commit #10's own execute(), which
    re-runs its own full input-validation/policy gate regardless of
    whether prepare() was ever called first, so a capability prepare()
    would have rejected is rejected there too, on its own merits, not
    because this class remembered a prior verdict.

    dependency_status and compatibility are computed once per resolved
    capability, directly through Commit #4/#5's own real services, and
    reused for both this result's own explicit fields and for deciding
    eligible_candidates -- never re-derived a second, different way.
    Commit #6's own select() independently re-checks compatibility for
    whatever candidates it is given (its own established behavior,
    unchanged) -- a harmless, deterministic re-confirmation of the exact
    same already-real verdict, not a second implementation of it.

    No background workers, queues, or schedulers: every method here
    runs synchronously, to completion, within one call -- the same "no
    invented runtime infrastructure" discipline every commit in this
    whole subsystem has kept since Commit #1.
    """

    def __init__(
        self,
        capability_registry: LLMAgentCapabilityRegistry,
        capability_resolver: LLMAgentCapabilityResolver,
        dependency_service: LLMAgentCapabilityDependencyService,
        compatibility: LLMAgentCapabilityCompatibility,
        selector: LLMAgentCapabilitySelector,
        execution_lifecycle: LLMAgentCapabilityExecutionLifecycleService,
        execution_control: LLMAgentCapabilityExecutionControl,
    ):
        self._capability_registry = capability_registry
        self._capability_resolver = capability_resolver
        self._dependency_service = dependency_service
        self._compatibility = compatibility
        self._selector = selector
        self._execution_lifecycle = execution_lifecycle
        self._execution_control = execution_control

    def prepare(self, agent_id: str, scope_id: str, task_context: dict) -> CapabilityPreparationResult:
        """Coordinate resolution -> dependency/contract checks ->
        compatibility -> selection for one agent/scope/task.

        Raises:
            InvalidCapabilityResolutionError: Propagated unchanged from
                LLMAgentCapabilityResolver.resolve() (blank agent_id/
                scope_id, or task_context not a dict)
        """
        resolved = self._capability_resolver.resolve(agent_id, scope_id, task_context)
        resolved_capabilities = [capability.capability_id for capability in resolved.capabilities]

        dependency_status = {}
        compatibility = {}
        rejections = {}
        eligible_candidates = []

        for capability_id in resolved_capabilities:
            dependency_result = self._dependency_service.validate_dependencies([capability_id])
            dependency_status[capability_id] = dependency_result

            compatibility_result = self._compatibility.check(capability_id, agent_id, scope_id, task_context)
            compatibility[capability_id] = compatibility_result

            if not dependency_result.valid:
                rejections[capability_id] = (
                    f"dependency check failed: missing={dependency_result.missing_capabilities}, "
                    f"cycles={dependency_result.cycles}, unresolved={dependency_result.unresolved_dependencies}"
                )
                continue

            if not compatibility_result.compatible:
                rejections[capability_id] = (
                    f"compatibility check failed: {compatibility_result.failed_checks}"
                )
                continue

            eligible_candidates.append(capability_id)

        selection = self._selector.select(agent_id, scope_id, task_context, candidates=eligible_candidates)
        for capability_id in selection.rejected_capabilities:
            rejections.setdefault(capability_id, selection.selection_reasons.get(capability_id, "rejected by selector"))

        return CapabilityPreparationResult(
            resolved_capabilities=resolved_capabilities,
            selected_capabilities=selection.selected_capabilities,
            compatibility=compatibility,
            dependency_status=dependency_status,
            rejections=rejections,
        )

    def execute_selected(
        self, agent_id: str, scope_id: str, capability_id: str, input_payload, context: dict = None
    ) -> CapabilityExecutionResult:
        """Execute capability_id for agent_id in scope_id -- pure
        delegation to Commit #10's own
        LLMAgentCapabilityExecutionLifecycleService.execute(), which
        re-runs its own full resolve/validate/policy/execute/validate
        pipeline regardless of whether prepare() selected capability_id
        or not.
        """
        return self._execution_lifecycle.execute(agent_id, capability_id, scope_id, input_payload, context)

    def control(self, execution_id: str, action: str) -> ExecutionControlResult:
        """Cancel or check the timeout of execution_id -- pure
        delegation to Commit #12's own LLMAgentCapabilityExecutionControl.

        Raises:
            InvalidCapabilityOrchestrationError: If action is not
                "cancel" or "check_timeout"
        """
        if action == ACTION_CANCEL:
            return self._execution_control.cancel(execution_id)
        if action == ACTION_CHECK_TIMEOUT:
            return self._execution_control.check_timeout(execution_id)
        raise InvalidCapabilityOrchestrationError(
            f"action must be one of {sorted(CONTROL_ACTIONS)}, got {action!r}"
        )
