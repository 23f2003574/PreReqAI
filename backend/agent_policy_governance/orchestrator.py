from backend.agent_policy_audit import LLMAgentPolicyAuditService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement, is_blocking

from .models import GovernanceResult


class NoExecutionBoundaryConfiguredError(ValueError):
    """Raised by execute_step() when this orchestrator was built without
    an execution_service -- evaluate_action() alone never needs one."""


class NoLifecycleServiceConfiguredError(ValueError):
    """Raised by metrics()/report()/versions()/rollback() when this
    orchestrator was built without the corresponding optional service."""


class LLMAgentPolicyGovernanceOrchestrator:
    """The single governance facade over Commits #1-#12: composes
    resolution, evaluation, exception handling, enforcement, auditing,
    and (optionally) metrics/reporting/versioning/rollback into one
    coherent surface, without reimplementing a single one of them.

    Not a workflow engine, and not a second execution pipeline: every
    collaborator here is an already-built Commit #1-#12 service, wired
    together the exact same way every earlier commit in this series
    already composes the one before it (Commit #4 wraps #1-#3, Commit #5
    plugs into Commit #4's own extension point, Commit #7 subclasses
    Commit #4, Commit #12 is built entirely on Commit #11). This class
    adds no new resolution, decision, exception, enforcement, audit,
    metrics, reporting, versioning, or rollback logic of its own -- it
    only decides which already-built method to call, in which order, and
    how to shape what comes back.

    evaluate_action(action_context) runs exactly the flow this commit's
    own goal describes, and no more:

        resolve policies -> evaluate decision -> apply active exception
            all three are LLMAgentPolicyEnforcement.enforce() itself
            (Commit #2's resolver + Commit #3's decision engine,
            optionally Commit #5's exception-aware one if that is what
            `enforcement` was constructed with) -- called exactly once,
            never re-implemented here
        enforce decision
            is_blocking(decision), Commit #4's own predicate, reused
            verbatim rather than re-deriving "does this actually stop
            the action" from decision.decision a second, subtly
            different way
        audit decision
            LLMAgentPolicyAuditService.record(), Commit #7's own method,
            called with whatever execution_id/action_id action_context
            supplies -- best-effort: a failure recording the audit can
            never change the GovernanceResult already computed, the
            exact same "audit failure does not change decision"
            discipline Commit #7's own LLMAgentPolicyAuditedExecutionService
            already applies at the real execution boundary
        expose result/provenance
            GovernanceResult, bundling the full PolicyDecision (already
            complete provenance from Commits #1-#5), the blocked
            verdict, and the audit record (or None) into one object

    A genuine policy-evaluation failure (LLMAgentPolicyEnforcement.enforce()
    raising PolicyEvaluationFailedError) is never caught here: Commit #4
    already decided that failing to evaluate policy must fail closed and
    be visible to the caller, and this orchestrator does not weaken that
    -- only the *audit-recording* step is best-effort, never the
    evaluation itself.

    execute_step() is this orchestrator's own real execution-boundary
    integration: it delegates entirely to execution_service (typically a
    Commit #7 LLMAgentPolicyAuditedExecutionService, itself built on
    Commit #4's LLMAgentPolicyEnforcedExecutionService and Commit #1's
    LLMAgentExecutionService) -- "denied actions never execute" and
    "existing agent behavior remains unchanged when governance has no
    applicable restriction" both hold because they already hold for that
    service, unconditionally, and nothing here intercepts or second-
    guesses its result.

    metrics()/report()/versions()/rollback() are thin pass-throughs to
    whichever of Commit #8/#9/#11/#12's services this orchestrator was
    given -- administrative/lifecycle operations, never invoked as part
    of evaluate_action()'s own per-action flow, since none of them are
    meant to run on every single action.
    """

    def __init__(
        self,
        enforcement: LLMAgentPolicyEnforcement,
        audit_service: LLMAgentPolicyAuditService,
        execution_service=None,
        metrics_service=None,
        report_service=None,
        version_service=None,
        rollback_service=None,
    ):
        """
        Args:
            enforcement: Commit #4's LLMAgentPolicyEnforcement, already
                constructed with whichever Commit #2 resolver and Commit
                #3/#5 decision engine a caller wants governed
            audit_service: Commit #7's LLMAgentPolicyAuditService
            execution_service: Optional real execution boundary --
                typically a Commit #7 LLMAgentPolicyAuditedExecutionService
                (or Commit #4's own LLMAgentPolicyEnforcedExecutionService
                if a caller does not want per-step auditing duplicated).
                Any object exposing execute_step(plan_id, step_id,
                subject, timeout=None) is accepted. Required only for
                execute_step()
            metrics_service: Optional Commit #8 LLMAgentPolicyMetricsService
            report_service: Optional Commit #9 LLMAgentPolicyReportService
            version_service: Optional Commit #11 LLMAgentPolicyVersionService
            rollback_service: Optional Commit #12 LLMAgentPolicyRollbackService
        """
        self._enforcement = enforcement
        self._audit_service = audit_service
        self._execution_service = execution_service
        self._metrics_service = metrics_service
        self._report_service = report_service
        self._version_service = version_service
        self._rollback_service = rollback_service

    def evaluate_action(self, action_context: dict) -> GovernanceResult:
        """Resolve, decide, except, enforce-check, and audit one action,
        without ever reaching a real execution boundary.

        Raises:
            InvalidPolicyDecisionInputError: If action_context is not a
                dict (propagated from enforce(), not wrapped)
            PolicyEvaluationFailedError: If resolving or evaluating
                policy itself fails unexpectedly (propagated from
                enforce(), not wrapped -- a policy-evaluation failure is
                never silently absorbed into an ALLOW-looking result)
        """
        decision = self._enforcement.enforce(action_context)
        blocked = is_blocking(decision)

        scope_id = action_context.get("scope_id")
        execution_or_action_id = action_context.get("execution_id") or action_context.get("action_id")

        audit_record = None
        if execution_or_action_id:
            try:
                audit_record = self._audit_service.record(scope_id, execution_or_action_id, decision)
            except Exception:
                audit_record = None

        return GovernanceResult(
            action_context=dict(action_context),
            scope_id=scope_id,
            execution_or_action_id=execution_or_action_id,
            decision=decision,
            blocked=blocked,
            audit=audit_record,
        )

    def execute_step(self, plan_id: str, step_id: str, subject, timeout: float = None):
        """Run one real plan step through the configured execution
        boundary -- denied actions never execute, and existing behavior
        is unchanged when nothing applicable blocks it, exactly as
        execution_service's own contract already guarantees.

        Raises:
            NoExecutionBoundaryConfiguredError: If this orchestrator was
                built without an execution_service
        """
        if self._execution_service is None:
            raise NoExecutionBoundaryConfiguredError(
                "this orchestrator was not configured with an execution_service"
            )
        return self._execution_service.execute_step(plan_id, step_id, subject, timeout=timeout)

    def metrics(self, scope_id: str, filters: dict = None):
        """Pass through to Commit #8's LLMAgentPolicyMetricsService.summarize()."""
        if self._metrics_service is None:
            raise NoLifecycleServiceConfiguredError("this orchestrator was not configured with a metrics_service")
        return self._metrics_service.summarize(scope_id, filters)

    def report(self, scope_id: str, filters: dict = None):
        """Pass through to Commit #9's LLMAgentPolicyReportService.generate()."""
        if self._report_service is None:
            raise NoLifecycleServiceConfiguredError("this orchestrator was not configured with a report_service")
        return self._report_service.generate(scope_id, filters)

    def versions(self, policy_id: str):
        """Pass through to Commit #11's LLMAgentPolicyVersionService.list_versions()."""
        if self._version_service is None:
            raise NoLifecycleServiceConfiguredError("this orchestrator was not configured with a version_service")
        return self._version_service.list_versions(policy_id)

    def rollback(self, policy_id: str, target_version: int, reason: str, actor: str = None):
        """Pass through to Commit #12's LLMAgentPolicyRollbackService.rollback()."""
        if self._rollback_service is None:
            raise NoLifecycleServiceConfiguredError("this orchestrator was not configured with a rollback_service")
        return self._rollback_service.rollback(policy_id, target_version, reason, actor=actor)
