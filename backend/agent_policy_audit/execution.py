from backend.agent_policy_enforcement import LLMAgentPolicyEnforcedExecutionService

from .service import LLMAgentPolicyAuditService


class LLMAgentPolicyAuditedExecutionService(LLMAgentPolicyEnforcedExecutionService):
    """Commit #4's LLMAgentPolicyEnforcedExecutionService, unchanged,
    with exactly one more step after a real step completes: recording an
    append-only Commit #7 audit entry for the policy decision that
    governed it.

    Not a second execution pipeline, and Commit #4 is never modified:
    execute_step() here delegates the entire gate-then-execute sequence
    to super().execute_step() first, completely unchanged -- the
    returned LLMAgentStepExecution (and its real execution_id) already
    reflects Commit #4's own decision by the time any audit code runs.
    Only afterward does this method re-run the exact same, pure,
    side-effect-free LLMAgentPolicyEnforcement.enforce() call Commit #4's
    own execute_step() already made internally, solely to obtain the
    PolicyDecision object to audit (enforce() has no way to hand that
    decision back out through execute_step()'s own return value).
    enforce() is deterministic and side-effect free (Commit #4), so
    calling it again for the identical action_context can never reach a
    different verdict, or change the result super().execute_step()
    already returned and already committed to -- "auditing must not
    change the enforcement result" holds by construction, not by
    convention. This trades one extra, cheap, pure call for never having
    to modify Commit #4's own already-tested execute_step() to expose an
    internal decision.

    Recording is wrapped so a failure in the audit store can never
    surface to the caller or change the already-finalized step result:
    "audit failure does not change decision" holds for the same reason --
    the audit call happens strictly after execute_step()'s own return
    value already exists, and any exception raised while building the
    audit's inputs or writing it is swallowed rather than propagated.
    """

    def __init__(
        self,
        planning_service,
        validation_service,
        tool_orchestration_service,
        enforcement,
        scope_for_plan,
        audit_service: LLMAgentPolicyAuditService,
    ):
        super().__init__(planning_service, validation_service, tool_orchestration_service, enforcement, scope_for_plan)
        self._audit_service = audit_service

    def execute_step(self, plan_id: str, step_id: str, subject, timeout: float = None):
        result = super().execute_step(plan_id, step_id, subject, timeout=timeout)

        try:
            plan = self._planning_service.get(plan_id)
            step = self._find_step(plan, step_id)
            scope_id = self._scope_for_plan(plan_id)
            action_context = {
                "scope_id": scope_id,
                "plan_id": plan_id,
                "step_id": step_id,
                "tool_name": step.tool_name,
                "arguments": dict(step.arguments),
                "subject": subject,
            }
            decision = self._enforcement.enforce(action_context)
            self._audit_service.record(scope_id, result.execution_id, decision)
        except Exception:
            pass

        return result
