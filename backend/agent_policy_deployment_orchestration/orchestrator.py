from backend.agent_policy_deployment_governance import (
    KEEP,
    LLMAgentPolicyDeploymentGovernance,
    ROLLBACK_RECOMMENDED as GOVERNANCE_ROLLBACK_RECOMMENDED,
)
from backend.agent_policy_deployment_health import LLMAgentPolicyDeploymentHealth
from backend.agent_policy_deployment_history import (
    DEPLOYMENT_SUCCEEDED,
    LLMAgentPolicyDeploymentHistory,
    UnknownDeploymentRecordError,
)
from backend.agent_policy_deployment_rollback import LLMAgentPolicyDeploymentRollbackService
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_template_deployment import LLMAgentPolicyTemplateDeploymentService

from .models import (
    DEGRADED,
    DEPLOY_FAILED,
    ROLLBACK_FAILED,
    ROLLBACK_RECOMMENDED,
    ROLLED_BACK,
    SUCCEEDED,
    VERIFICATION_FAILED,
    DeploymentResult,
)


class LLMAgentPolicyDeploymentOrchestrator:
    """The single real entry point for the whole template -> policy
    deployment lifecycle this series has built: deploy (Commit #7) ->
    verify (Commit #9) -> assess health (Commit #11) -> govern the
    result (Commit #12) -> roll back only when explicitly authorized
    (Commit #10). Every stage is an already-built collaborator, called
    exactly once, in exactly this order -- "compose Commit #7-#12; keep
    business logic in those services" holds because this class contains
    none of its own: no rule validation, no compatibility checking, no
    health scoring, no governance policy, no rollback mechanics.

    "validate" (the flow's own first named stage) is not a separate call
    this orchestrator makes -- it is already the first thing Commit #7's
    own deploy() does internally (load, validate policy, verify target
    compatibility) before this orchestrator ever sees a result. Re-running
    it here would be exactly the "duplicate logic from individual
    services" the Rules forbid.

    status is derived from governance.decision first, then refined by
    verification.verified where governance's own INVESTIGATE covers two
    genuinely different situations it does not itself distinguish by
    name: INVESTIGATE with a failed verification (VERIFICATION_FAILED)
    vs. INVESTIGATE with verification passing but health degraded
    (DEGRADED, e.g. recent deployment failures to this same slot).
    ROLLBACK_RECOMMENDED (governance's own decision) always implies
    verification failed too, per Commit #12's own logic -- but is
    reported as ROLLBACK_RECOMMENDED / ROLLED_BACK / ROLLBACK_FAILED,
    never folded into the generic VERIFICATION_FAILED, since it carries
    the more specific and more actionable meaning "there is a prior
    good deployment to consider restoring." "Failed verification
    prevents successful completion" and "health/governance failures
    must not be hidden" both hold because SUCCEEDED is reachable only
    through the single governance.decision == KEEP branch.

    Automatic rollback is gated by rollback_authorization, an optional,
    explicitly-supplied callable: (deployment_id, GovernanceResult) ->
    bool. This repository has no pre-existing generic "is this action
    authorized" mechanism to reuse (inspected: the closest matches --
    backend.llm.tool_permissions, the various backend.session
    execution_secret_*/execution_approval_delegation_* services -- are
    all domain-specific to tool calls or secrets/artifacts, not to
    deployment rollback), so per the Rule's own conditional ("only if the
    repository already has" such a mechanism), automatic rollback is
    never attempted unless a caller explicitly wires one in at
    construction time; rollback_authorization defaults to None, and
    governance recommending a rollback with no such collaborator
    configured (or one that declines, or no restorable target can even
    be resolved) always surfaces as ROLLBACK_RECOMMENDED, never a silent
    no-op and never an automatic action taken on this orchestrator's own
    initiative. The resolved rollback target (or the fact that none
    could be found) is always exposed in provenance regardless of
    whether a rollback_service/rollback_authorization is even
    configured -- "expose each stage's result and provenance" holds even
    when this orchestrator was never equipped to act on it.

    Commit #10's own rollback(deployment_id, reason) restores TO
    deployment_id -- it is never the currently-failing deployment being
    orchestrated. This orchestrator resolves the actual restoration
    target itself, via Commit #8's own history (the most recent prior
    DEPLOYMENT_SUCCEEDED record for the same scope/template slot, older
    than the one governance flagged) -- reusing Commit #8's own already-
    scope-isolated list_for_scope() rather than re-deriving Commit #12's
    own "is there a plausible prior deployment" count into something it
    was never meant to expose.

    Idempotency is inherited entirely from Commit #7's own deploy() (a
    repeated call for an already-current policy_id returns
    ALREADY_DEPLOYED without re-archiving anything) -- this orchestrator
    adds no idempotency logic of its own, it simply never interferes
    with what deploy() already guarantees.
    """

    def __init__(
        self,
        deployment_service: LLMAgentPolicyTemplateDeploymentService,
        history_service: LLMAgentPolicyDeploymentHistory,
        verifier: LLMAgentPolicyDeploymentVerifier,
        health_service: LLMAgentPolicyDeploymentHealth,
        governance_service: LLMAgentPolicyDeploymentGovernance,
        rollback_service: LLMAgentPolicyDeploymentRollbackService = None,
        rollback_authorization=None,
    ):
        self._deployment_service = deployment_service
        self._history_service = history_service
        self._verifier = verifier
        self._health_service = health_service
        self._governance_service = governance_service
        self._rollback_service = rollback_service
        self._rollback_authorization = rollback_authorization

    def deploy(self, policy_id: str, target_context: dict) -> DeploymentResult:
        scope_id = target_context.get("scope_id") if isinstance(target_context, dict) else None

        try:
            deploy_result = self._deployment_service.deploy(policy_id, target_context)
        except Exception as error:
            return DeploymentResult(
                policy_id=policy_id,
                scope_id=scope_id,
                status=DEPLOY_FAILED,
                reasons=[f"deployment failed: {error}"],
                provenance={},
            )

        deployment_id = deploy_result.deployment_id
        verification = self._verifier.verify(deployment_id)
        health = self._health_service.assess(deployment_id)
        governance = self._governance_service.evaluate(deployment_id)

        provenance = {
            "deploy_result": deploy_result.to_dict(),
            "verification": verification.to_dict(),
            "health": health.to_dict(),
            "governance": governance.to_dict(),
        }
        reasons = list(governance.reasons)

        if governance.decision == KEEP:
            status = SUCCEEDED
        elif governance.decision == GOVERNANCE_ROLLBACK_RECOMMENDED:
            status = ROLLBACK_RECOMMENDED
        elif not verification.verified:
            status = VERIFICATION_FAILED
        else:
            status = DEGRADED

        rollback_result = None
        if status == ROLLBACK_RECOMMENDED:
            target_deployment_id = self._resolve_rollback_target(deployment_id)
            provenance["rollback_target_deployment_id"] = target_deployment_id

            if target_deployment_id is None:
                reasons.append("governance recommended rollback but no restorable prior deployment could be resolved")
            elif self._rollback_service is not None and self._is_rollback_authorized(deployment_id, governance):
                try:
                    rollback_result = self._rollback_service.rollback(
                        target_deployment_id,
                        reason=f"automatic rollback: governance recommended it ({'; '.join(governance.reasons)})",
                        actor="agent_policy_deployment_orchestrator",
                    )
                    status = ROLLED_BACK
                    provenance["rollback"] = rollback_result.to_dict()
                except Exception as error:
                    status = ROLLBACK_FAILED
                    reasons.append(f"authorized rollback failed: {error}")

        return DeploymentResult(
            policy_id=deploy_result.policy_id,
            scope_id=deploy_result.scope_id,
            status=status,
            deploy_result=deploy_result,
            verification=verification,
            health=health,
            governance=governance,
            rollback=rollback_result,
            reasons=reasons,
            provenance=provenance,
        )

    def _resolve_rollback_target(self, deployment_id: str):
        try:
            record = self._history_service.get(deployment_id)
        except UnknownDeploymentRecordError:
            return None
        if record.template_id is None:
            return None

        candidates = sorted(
            (
                other
                for other in self._history_service.list_for_scope(record.target_scope)
                if other.status == DEPLOYMENT_SUCCEEDED
                and other.template_id == record.template_id
                and other.created_at < record.created_at
            ),
            key=lambda other: other.created_at,
        )
        return candidates[-1].deployment_id if candidates else None

    def _is_rollback_authorized(self, deployment_id: str, governance) -> bool:
        if self._rollback_authorization is None:
            return False
        try:
            return bool(self._rollback_authorization(deployment_id, governance))
        except Exception:
            return False
