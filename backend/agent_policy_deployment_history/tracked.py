from backend.agent_policy_template_deployment import LLMAgentPolicyTemplateDeploymentService

from .models import DEPLOYMENT_FAILED, DEPLOYMENT_SUCCEEDED
from .service import LLMAgentPolicyDeploymentHistory


class LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(LLMAgentPolicyTemplateDeploymentService):
    """Commit #7's LLMAgentPolicyTemplateDeploymentService, unchanged,
    with exactly one more step around deploy(): recording an append-only
    LLMAgentPolicyDeploymentRecord for the attempt, successful or
    failed.

    Not a second deployment service, and Commit #7 is never modified:
    deploy() here delegates the entire load -> validate -> compatibility
    -> activate sequence to super().deploy() first, completely
    unchanged. Only afterward -- on either the real return value or the
    real raised exception -- does this method record anything, the same
    "delegate first, then record, best-effort" shape
    backend.agent_policy_history.LLMAgentPolicyHistoryTrackedService and
    backend.agent_policy_audit.LLMAgentPolicyAuditedExecutionService
    already establish elsewhere in this series -- extended here to cover
    a failed attempt too, which neither of those existing wrappers had
    any need to.

    Recording a SUCCESS is best-effort exactly like those two
    precedents: a failure writing the record can never surface to the
    caller or retroactively undo the deployment super().deploy() already
    completed -- "recording failure must not falsely report deployment
    success" holds in that direction because the real result already
    exists, in full, before any recording code runs.

    Recording a FAILURE is best-effort in the *same* sense -- a further
    failure while trying to record the original failure never replaces
    or masks it -- but the original exception super().deploy() raised is
    always re-raised afterward, never swallowed: recording a failed
    attempt must never turn it into an apparent success, so this method
    never returns normally after super().deploy() itself raised.

    template_id/template_version, when they cannot be resolved from a
    successful DeploymentResult (a failed attempt has none), are looked
    up best-effort from this same object's own inherited _instantiator/
    _template_service (Commit #6/#1) -- reusing Commit #7's own
    collaborators verbatim, never a second provenance lookup path. When
    even that fails (e.g. policy_id itself is unknown), both stay None
    rather than raising out of the recording path.

    reason/actor are optional, purely additive parameters on deploy()
    (Commit #7's own base signature is never changed) -- when a caller
    supplies them (Commit #10's own rollback is the first to), they are
    forwarded verbatim onto whichever record this call produces, success
    or failure alike.
    """

    def __init__(self, *args, history_service: LLMAgentPolicyDeploymentHistory = None, version_service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._history_service = history_service if history_service is not None else LLMAgentPolicyDeploymentHistory()
        self._version_service = version_service

    def deploy(self, policy_id: str, target_context: dict, reason: str = None, actor: str = None):
        target_scope = target_context.get("scope_id") if isinstance(target_context, dict) else None

        try:
            result = super().deploy(policy_id, target_context)
        except Exception as error:
            template_id, template_version = self._peek_template(policy_id)
            self._safe_record(
                policy_id=policy_id,
                target_scope=target_scope or "unknown",
                status=DEPLOYMENT_FAILED,
                template_id=template_id,
                template_version=template_version,
                provenance={"reason": str(error)},
                reason=reason,
                actor=actor,
            )
            raise

        self._safe_record(
            policy_id=result.policy_id,
            target_scope=result.scope_id,
            status=DEPLOYMENT_SUCCEEDED,
            template_id=result.template_id,
            template_version=result.template_version,
            policy_version=self._peek_policy_version(result.policy_id),
            provenance={"deployment_status": result.status, "previous_policy_id": result.previous_policy_id},
            deployment_id=result.deployment_id,
            reason=reason,
            actor=actor,
        )
        return result

    def _peek_template(self, policy_id: str):
        try:
            instantiation_record = self._instantiator.provenance(policy_id)
            template = self._template_service.get(instantiation_record.resolved_template_id)
            return template.template_id, template.version
        except Exception:
            return None, None

    def _peek_policy_version(self, policy_id: str):
        if self._version_service is None:
            return None
        try:
            versions = self._version_service.list_versions(policy_id)
            return versions[-1].version if versions else None
        except Exception:
            return None

    def _safe_record(self, **kwargs) -> None:
        try:
            self._history_service.record(**kwargs)
        except Exception:
            pass
