from backend.agent_policy_deployment_history import DEPLOYMENT_FAILED, LLMAgentPolicyDeploymentHistory, UnknownDeploymentRecordError
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import ACTIVE
from backend.agent_policy_template_deployment import LLMAgentPolicyTemplateDeploymentService
from backend.agent_policy_templates import LLMAgentPolicyTemplateService, UnknownPolicyTemplateError

from .models import DEGRADED, HEALTHY, UNHEALTHY, UNKNOWN, HealthResult, overall_status


class LLMAgentPolicyDeploymentHealth:
    """A single healthy/degraded/unhealthy/unknown verdict for one Commit
    #8 deployment record, combining Commit #7-#10's own existing
    evidence -- never a new observability, metrics, or monitoring system.

    Mirrors backend.llm.security_health.LLMSecurityHealthService, the
    closest existing health-assessment precedent in this repository:
    every input is an already-existing aggregate or record this class
    reads and combines, never something it computes or detects on its
    own, and overall status is decided by a fixed severity order (worst
    signal wins) via this module's own overall_status(), never a bespoke
    per-call ranking.

    assess(deployment_id) reads exactly four pieces of already-durable
    evidence, and adds none of its own:

        "deployment status"
            The Commit #8 record's own status -- a DEPLOYMENT_FAILED
            record is UNHEALTHY outright, with nothing further to check
            (no policy was ever actually activated by it).
        "verification result" / "active policy/version consistency"
            Commit #9's own LLMAgentPolicyDeploymentVerifier.verify(),
            called with require_active=False (the same flag Commit #10
            added for its own rollback-target check) -- a mismatched
            scope, invalid rules, or template/version provenance drift
            is UNHEALTHY regardless of the policy's current ACTIVE/
            ARCHIVED status, which is judged separately, together with
            "rollback state" below, from this same verify() call's own
            provenance["policy_status"]. Collapsing both into verify()'s
            own stricter require_active=True default would make an
            intentionally-superseded deployment indistinguishable from a
            genuinely broken one -- exactly the distinction the next
            check exists to draw. "A failed verification cannot produce
            healthy" holds by construction either way, since UNHEALTHY
            is the single worst signal overall_status() ever returns.
        "rollback state" / "active policy/version consistency"
            Commit #7's own DeploymentService.current_for(scope,
            template_name), combined with the real policy_status
            verify() already read: if this deployment's policy_id is
            still supposed to be the slot's current one but is not
            actually ACTIVE, that is a genuine inconsistency --
            UNHEALTHY. If it is simply no longer the slot's current one
            at all, it has been properly superseded or rolled back away
            from -- DEGRADED, never UNHEALTHY on its own, since
            intentional supersession is expected lifecycle, not a
            malfunction.
        "recent deployment failures"
            Commit #8's own history_service.list_for_scope(): any
            DEPLOYMENT_FAILED record for the same (scope, template)
            slot with a created_at strictly after this deployment's own
            -- i.e. a later attempt to redeploy this same slot has since
            failed -- contributes DEGRADED. "Recent" is defined
            structurally (relative to this deployment's own timestamp),
            never by wall-clock age, so assess() stays deterministic:
            repeated calls against unchanged history always agree.

    Every check above that needs a piece of evidence it cannot resolve
    (e.g. a record with no template_id at all, because Commit #8 itself
    could never resolve one) is skipped entirely rather than assumed --
    "do not infer health from unavailable evidence" holds because a
    skipped check contributes no signal at all, not a guessed HEALTHY.
    A deployment_id with no Commit #8 record at all returns UNKNOWN,
    with no other check attempted (there is nothing to combine it with).

    assess_scope(scope_id) is a thin, read-only fan-out: it assesses
    every deployment record Commit #8's own
    history_service.list_for_scope(scope_id) already returns (oldest
    first, the same ordering that store already guarantees) -- never a
    second scope-listing mechanism, and scope-isolated exactly because
    list_for_scope() itself already is.
    """

    def __init__(
        self,
        deployment_service: LLMAgentPolicyTemplateDeploymentService,
        history_service: LLMAgentPolicyDeploymentHistory,
        verifier: LLMAgentPolicyDeploymentVerifier,
        template_service: LLMAgentPolicyTemplateService,
    ):
        self._deployment_service = deployment_service
        self._history_service = history_service
        self._verifier = verifier
        self._template_service = template_service

    def assess(self, deployment_id: str) -> HealthResult:
        try:
            record = self._history_service.get(deployment_id)
        except UnknownDeploymentRecordError:
            return HealthResult(
                deployment_id=deployment_id, status=UNKNOWN,
                reasons=[f"no deployment record was ever recorded for deployment_id {deployment_id!r}"],
            )

        provenance = {"recorded_status": record.status}

        if record.status == DEPLOYMENT_FAILED:
            return HealthResult(
                deployment_id=deployment_id,
                status=UNHEALTHY,
                policy_id=record.policy_id,
                scope_id=record.target_scope,
                template_id=record.template_id,
                template_version=record.template_version,
                reasons=["this deployment attempt failed and never activated a policy"],
                provenance=provenance,
            )

        signals = set()
        reasons = []

        # require_active=False: whether this deployment's policy is
        # *currently* ACTIVE is judged separately below, together with
        # whether it is even still supposed to be -- collapsing both
        # into verify()'s own stricter default would make an
        # intentionally-superseded deployment (see "rollback state"
        # below) indistinguishable from a genuinely broken one.
        verification = self._verifier.verify(deployment_id, require_active=False)
        provenance["verification"] = verification.to_dict()
        if not verification.verified:
            signals.add(UNHEALTHY)
            reasons.append(f"verification failed: {'; '.join(verification.reasons)}")

        template_name = self._resolve_template_name(record.template_id)
        if template_name is not None:
            current_policy_id = self._deployment_service.current_for(record.target_scope, template_name)
            provenance["current_policy_id"] = current_policy_id
            policy_status = verification.provenance.get("policy_status")

            if current_policy_id == record.policy_id:
                if policy_status is not None and policy_status != ACTIVE:
                    signals.add(UNHEALTHY)
                    reasons.append(
                        f"this deployment is still supposed to be active for its slot, but its "
                        f"policy is {policy_status!r}"
                    )
            else:
                signals.add(DEGRADED)
                reasons.append("this deployment is no longer the active one for its scope/template slot")

            later_failures = [
                other
                for other in self._history_service.list_for_scope(record.target_scope)
                if other.status == DEPLOYMENT_FAILED
                and other.template_id == record.template_id
                and other.created_at > record.created_at
            ]
            provenance["later_failure_count"] = len(later_failures)
            if later_failures:
                signals.add(DEGRADED)
                reasons.append(
                    f"{len(later_failures)} deployment attempt(s) to this same slot failed after this "
                    f"one went live"
                )

        return HealthResult(
            deployment_id=deployment_id,
            status=overall_status(signals) if signals else HEALTHY,
            policy_id=record.policy_id,
            scope_id=record.target_scope,
            template_id=record.template_id,
            template_version=record.template_version,
            reasons=reasons,
            provenance=provenance,
        )

    def assess_scope(self, scope_id: str) -> list:
        """Every HealthResult for scope_id's own deployment history,
        oldest first -- never a record from any other scope."""
        return [self.assess(record.deployment_id) for record in self._history_service.list_for_scope(scope_id)]

    def _resolve_template_name(self, template_id: str):
        if template_id is None:
            return None
        try:
            return self._template_service.get(template_id).name
        except UnknownPolicyTemplateError:
            return None
