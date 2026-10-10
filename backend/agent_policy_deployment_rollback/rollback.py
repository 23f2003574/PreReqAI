from backend.agent_policy_deployment_history import LLMAgentPolicyDeploymentHistory, UnknownDeploymentRecordError
from backend.agent_policy_deployment_history.tracked import LLMAgentPolicyDeploymentHistoryTrackedDeploymentService
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import LLMAgentPolicyService
from backend.agent_policy_template_instantiation_pipeline import LLMAgentPolicyTemplateInstantiator
from backend.agent_policy_templates import LLMAgentPolicyTemplateService

from .models import ALREADY_CURRENT, ROLLED_BACK, RollbackResult


class LLMAgentPolicyDeploymentRollbackError(ValueError):
    """Raised when rollback() cannot be carried out safely -- an unknown
    or invalid target deployment, a target that fails Commit #9's own
    verification, an activation failure while restoring it, or a
    restored state that itself fails post-rollback verification. Chains
    the real underlying error as __cause__ (mirroring
    backend.agent_policy_rollback.LLMAgentPolicyRollbackError, the base
    series' own single-error-type rollback convention), so a caller who
    wants the specific reason can still find it.
    """


class LLMAgentPolicyDeploymentRollbackService:
    """Safely restores whichever policy is currently deployed for a
    (scope, template) slot back to a previously recorded, still-valid
    Commit #8 deployment -- without ever reactivating an ARCHIVED policy
    record directly (Commit #1 (base series) provides no such mechanism,
    by design: "reviving one requires a fresh create() call, not a
    mutation of the archived record").

    Built entirely on Commits #1/#6/#7/#8/#9's own methods, never a
    second deployment, activation, or history path:

        "verify target deployment"
            Commit #9's own LLMAgentPolicyDeploymentVerifier.verify(),
            called with require_active=False -- a target that was
            legitimately superseded (and is therefore ARCHIVED right
            now) is not thereby an invalid rollback target, but every
            other check (the deployment actually reached
            DEPLOYMENT_SUCCEEDED, its policy's rules are still valid,
            its recorded scope/template/version provenance still
            matches reality) still runs exactly as it would for any
            other verify() call. A target that fails this is rejected
            outright, before anything else is touched.
        "resolve previous valid deployment/version"
            Commit #7's own DeploymentService.current_for(scope,
            template_name) -- whatever policy_id (if any) currently
            occupies the slot the target is being restored into. Its own
            Commit #8 deployment record (if any) is looked up purely for
            this result's own source_* provenance fields; nothing about
            it is validated (it is being superseded, not restored).
        "restore through existing policy activation mechanism"
            Never a direct reactivation of the target's own (ARCHIVED)
            policy_id, since Commit #1 has no such mechanism. Instead,
            Commit #6's own LLMAgentPolicyTemplateInstantiator.instantiate()
            is called again, with the exact same template_id and
            parameters Commit #6's own provenance already recorded for
            the target policy_id -- deterministic, since the same
            template + the same parameters always substitute to the same
            rules (Commit #1's own str.format()-based substitution) --
            producing a fresh, ACTIVE, fully-provenanced policy_id with
            byte-identical content to what was originally deployed. That
            fresh policy_id is then deployed through Commit #7's own
            deploy() verbatim, which is what actually archives whatever
            currently occupies the slot and activates the new one --
            "restore through existing policy activation mechanism" is
            thus exactly Commit #7's own mechanism, applied to freshly
            reconstructed content rather than a second one.
        "record rollback provenance/history"
            Handled entirely by the same deploy() call above: it is
            given to a Commit #8 LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
            whose own deploy() (extended, purely additively, by this
            same commit) now accepts reason/actor and threads them onto
            the LLMAgentPolicyDeploymentRecord it records -- no second,
            duplicate history entry is created here.
        "verify restored state"
            Commit #9's own verify() again, this time with its default
            require_active=True, against the *new* deployment_id the
            restoring deploy() call just produced -- a restored state
            that itself fails verification raises rather than being
            reported as a success ("failed rollback must not falsely
            report success").

    Idempotent for an already-restored target: before attempting
    anything, this service compares the *content* (name and rules) of
    whatever policy currently occupies the slot against the target's own
    (still-readable, even while ARCHIVED) policy content. An exact match
    means the slot is already, in substance, what the target represents
    -- returned as status ALREADY_CURRENT, with no archive/instantiate/
    deploy call of any kind, so a repeated rollback() to the same target
    is a true no-op, not merely one that happens to end up in the same
    place via a fresh policy_id every time.

    Scope-safe by construction: every step above is scoped to exactly
    the target deployment's own recorded target_scope, and Commit #7's
    own (scope_id, template_name) keying means a rollback for one scope
    can never read, let alone archive or restore, anything belonging to
    another.
    """

    def __init__(
        self,
        policy_service: LLMAgentPolicyService,
        deployment_service: LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
        history_service: LLMAgentPolicyDeploymentHistory,
        verifier: LLMAgentPolicyDeploymentVerifier,
        template_service: LLMAgentPolicyTemplateService,
        instantiator: LLMAgentPolicyTemplateInstantiator,
    ):
        self._policy_service = policy_service
        self._deployment_service = deployment_service
        self._history_service = history_service
        self._verifier = verifier
        self._template_service = template_service
        self._instantiator = instantiator

    def rollback(self, deployment_id: str, reason: str, actor: str = None) -> RollbackResult:
        """Restore the (scope, template) slot deployment_id belongs to
        back to that deployment's own content.

        Raises:
            LLMAgentPolicyDeploymentRollbackError: If reason is missing,
                deployment_id was never recorded, the target fails
                Commit #9's own verification, restoring it fails, or the
                restored state itself fails verification
        """
        if not reason or not isinstance(reason, str):
            raise LLMAgentPolicyDeploymentRollbackError("reason is required to roll back a deployment")

        try:
            target_record = self._history_service.get(deployment_id)
        except UnknownDeploymentRecordError as error:
            raise LLMAgentPolicyDeploymentRollbackError(
                f"cannot roll back: deployment {deployment_id!r} was never recorded"
            ) from error

        target_verification = self._verifier.verify(deployment_id, require_active=False)
        if not target_verification.verified:
            raise LLMAgentPolicyDeploymentRollbackError(
                f"cannot roll back to deployment {deployment_id!r}: target failed verification: "
                f"{'; '.join(target_verification.reasons)}"
            )

        scope_id = target_record.target_scope
        template = self._template_service.get(target_record.template_id)
        target_policy = self._policy_service.get(target_record.policy_id)

        current_policy_id = self._deployment_service.current_for(scope_id, template.name)
        current_policy = self._policy_service.get(current_policy_id) if current_policy_id else None

        if current_policy is not None and self._same_content(current_policy, target_policy):
            source_deployment = self._safe_deployment_provenance(current_policy_id)
            verification = self._verifier.verify(source_deployment.deployment_id) if source_deployment else target_verification
            return RollbackResult(
                target_deployment_id=deployment_id,
                target_policy_id=target_record.policy_id,
                target_template_version=target_record.template_version,
                policy_id=current_policy_id,
                scope_id=scope_id,
                template_id=template.template_id,
                status=ALREADY_CURRENT,
                reason=reason,
                actor=actor,
                verification=verification,
            )

        source_deployment = self._safe_deployment_provenance(current_policy_id) if current_policy_id else None

        try:
            original_parameters = self._instantiator.provenance(target_record.policy_id).parameters
            fresh_policy = self._instantiator.instantiate(template.template_id, scope_id, original_parameters)
            deploy_result = self._deployment_service.deploy(
                fresh_policy.policy_id, {"scope_id": scope_id}, reason=reason, actor=actor,
            )
        except Exception as error:
            raise LLMAgentPolicyDeploymentRollbackError(
                f"cannot roll back to deployment {deployment_id!r}: activation failed: {error}"
            ) from error

        verification = self._verifier.verify(deploy_result.deployment_id)
        if not verification.verified:
            raise LLMAgentPolicyDeploymentRollbackError(
                f"rollback to deployment {deployment_id!r} completed but the restored state failed "
                f"verification: {'; '.join(verification.reasons)}"
            )

        return RollbackResult(
            target_deployment_id=deployment_id,
            target_policy_id=target_record.policy_id,
            target_template_version=target_record.template_version,
            policy_id=deploy_result.policy_id,
            scope_id=scope_id,
            template_id=template.template_id,
            status=ROLLED_BACK,
            reason=reason,
            actor=actor,
            verification=verification,
            source_deployment_id=source_deployment.deployment_id if source_deployment else None,
            source_policy_id=current_policy_id,
            source_template_version=source_deployment.template_version if source_deployment else None,
        )

    def _safe_deployment_provenance(self, policy_id: str):
        if policy_id is None:
            return None
        try:
            return self._deployment_service.provenance(policy_id)
        except Exception:
            return None

    @staticmethod
    def _same_content(policy_a, policy_b) -> bool:
        return policy_a.name == policy_b.name and [rule.to_dict() for rule in policy_a.rules] == [
            rule.to_dict() for rule in policy_b.rules
        ]
