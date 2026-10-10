from backend.agent_policy_deployment_health import HEALTHY, LLMAgentPolicyDeploymentHealth
from backend.agent_policy_deployment_history import (
    DEPLOYMENT_SUCCEEDED,
    LLMAgentPolicyDeploymentHistory,
    UnknownDeploymentRecordError,
)
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier

from .models import INVESTIGATE, KEEP, ROLLBACK_RECOMMENDED, GovernanceResult


class LLMAgentPolicyDeploymentGovernance:
    """The single governance decision for one deployment_id: keep it
    active, investigate it, or recommend rolling it back -- composing
    Commit #8's history, #9's verification, and #11's health, never
    reimplementing a single one of them.

    Mirrors the base agent_policy_* series' own Commit #13
    LLMAgentPolicyGovernanceOrchestrator: a pure composition root whose
    every collaborator is an already-built service, wired together to
    decide which existing method to call and how to combine what comes
    back -- no new detection, aggregation, or lifecycle logic of its
    own, and never a mutation of anything (see Rules: "read-only; do not
    perform rollback automatically" -- this class does not even hold a
    reference to Commit #10's own LLMAgentPolicyDeploymentRollbackService,
    since it never calls it; ROLLBACK_RECOMMENDED is advice for whoever
    holds one, never an action taken here).

    evaluate() runs exactly this flow, and no more:

        "verify deployment"
            Commit #9's own LLMAgentPolicyDeploymentVerifier.verify(),
            with its default require_active=True -- governance judges
            whether a deployment is safe to keep *as the currently live
            one*, the same strict sense Commit #10/#11 use
            require_active=False to deliberately relax for a historical
            target/superseded record, which this is not.
        "assess health"
            Commit #11's own LLMAgentPolicyDeploymentHealth.assess() --
            reused verbatim, including its own already-combined
            HEALTHY/DEGRADED/UNHEALTHY/UNKNOWN verdict and reasons.
        "inspect relevant deployment history"
            Only when verification failed: Commit #8's own
            history_service.list_for_scope(), filtered to
            DEPLOYMENT_SUCCEEDED records for the same template_id with
            an earlier created_at -- whether there is any prior, once-
            good deployment at all is what actually separates
            ROLLBACK_RECOMMENDED (something exists to roll back to) from
            INVESTIGATE (nothing does, so recommending a rollback would
            be advice with no real target).
        "return keep | investigate | rollback_recommended"
            KEEP only when verification succeeded AND health is HEALTHY.
            Verification succeeding with health DEGRADED (e.g. recent
            repeated deployment failures to this same slot, or any other
            Commit #11 signal that does not itself imply the live policy
            is unsafe) is INVESTIGATE, never KEEP and never
            ROLLBACK_RECOMMENDED -- the current state is not proven
            unsafe, only worth a human look. Any verification failure is
            never KEEP, resolved to ROLLBACK_RECOMMENDED or INVESTIGATE
            per the history inspection above. A deployment_id with no
            Commit #8 record at all is INVESTIGATE, with an explicit
            "no evidence" reason -- never guessed as either of the other
            two ("missing evidence must be explicit, not guessed").

    Scope-safe by construction: the only history inspection this class
    ever performs is scoped to the target deployment's own recorded
    target_scope, via Commit #8's own already scope-isolated
    list_for_scope().
    """

    def __init__(
        self,
        history_service: LLMAgentPolicyDeploymentHistory,
        verifier: LLMAgentPolicyDeploymentVerifier,
        health_service: LLMAgentPolicyDeploymentHealth,
    ):
        self._history_service = history_service
        self._verifier = verifier
        self._health_service = health_service

    def evaluate(self, deployment_id: str) -> GovernanceResult:
        verification = self._verifier.verify(deployment_id)
        health = self._health_service.assess(deployment_id)
        provenance = {"verification": verification.to_dict(), "health": health.to_dict()}

        try:
            record = self._history_service.get(deployment_id)
        except UnknownDeploymentRecordError:
            return GovernanceResult(
                deployment_id=deployment_id,
                decision=INVESTIGATE,
                reasons=[f"no deployment record was ever recorded for deployment_id {deployment_id!r}"],
                provenance=provenance,
            )

        common_fields = dict(scope_id=record.target_scope, policy_id=record.policy_id, template_id=record.template_id)

        if not verification.verified:
            reasons = [f"verification failed: {'; '.join(verification.reasons)}"]

            prior_successes = []
            if record.template_id is not None:
                prior_successes = [
                    other
                    for other in self._history_service.list_for_scope(record.target_scope)
                    if other.status == DEPLOYMENT_SUCCEEDED
                    and other.template_id == record.template_id
                    and other.created_at < record.created_at
                ]
            provenance["prior_successful_deployment_count"] = len(prior_successes)

            if prior_successes:
                decision = ROLLBACK_RECOMMENDED
                reasons.append(
                    f"{len(prior_successes)} earlier successful deployment(s) exist for this scope/template slot"
                )
            else:
                decision = INVESTIGATE
                reasons.append("no earlier successful deployment exists for this slot to roll back to")

            return GovernanceResult(
                deployment_id=deployment_id, decision=decision, reasons=reasons, provenance=provenance,
                **common_fields,
            )

        if health.status == HEALTHY:
            return GovernanceResult(
                deployment_id=deployment_id, decision=KEEP, reasons=[], provenance=provenance, **common_fields,
            )

        reasons = list(health.reasons) or [f"health status is {health.status!r}"]
        return GovernanceResult(
            deployment_id=deployment_id, decision=INVESTIGATE, reasons=reasons, provenance=provenance,
            **common_fields,
        )
