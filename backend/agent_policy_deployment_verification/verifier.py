from backend.agent_policy_deployment_history import DEPLOYMENT_SUCCEEDED, LLMAgentPolicyDeploymentHistory, UnknownDeploymentRecordError
from backend.agent_policy_engine import (
    ACTIVE,
    DuplicateRuleIdError,
    InvalidAgentPolicyError,
    InvalidPolicyRuleError,
    LLMAgentPolicyService,
    UnknownAgentPolicyError,
)
from backend.agent_policy_template_instantiation_pipeline import (
    LLMAgentPolicyTemplateInstantiator,
    UnknownTemplateInstantiationPipelineError,
)
from backend.agent_policy_templates import LLMAgentPolicyTemplateService, UnknownPolicyTemplateError

from .models import VerificationResult


class LLMAgentPolicyDeploymentVerifier:
    """Read-only, deterministic confirmation that a Commit #7 deployment
    -- as recorded by Commit #8's own append-only history -- is actually
    what it claims to be, right now, in the repository's real state.

    Not a second deployment or observability system: every fact this
    class checks is read directly from an already-existing source of
    truth, never a copy of its own --

        "deployment reached expected terminal state"
            Commit #8's own LLMAgentPolicyDeploymentHistory.get()
        "intended policy version is active" / "policy remains valid"
            Commit #1 (base series)'s own LLMAgentPolicyService.get()
            for the policy's current status, and its own
            _validate_rules() staticmethod (the exact same rule
            validation create()/update() already apply) re-run against
            the policy's current rules -- never a second rule-shape
            checker
        "template/version provenance matches"
            Commit #6's own LLMAgentPolicyTemplateInstantiator.provenance()
            plus Commit #1 (this series)'s own
            LLMAgentPolicyTemplateService.get(), the identical
            provenance chain Commit #7's own deploy() already resolves
            compatibility against
        "target scope is correct"
            The same real LLMAgentPolicyService.get() read, compared
            against Commit #8's own recorded target_scope

    verify() never mutates anything it reads, and never calls Commit #7's
    own deploy() -- purely a read, exactly "verification is read-only."
    Every check that can still be evaluated runs even after an earlier
    one already failed (e.g. a deployment stuck at DEPLOYMENT_FAILED
    still gets whatever provenance can be resolved from the record
    alone), so reasons always reports everything currently wrong, not
    just the first problem found -- "detect partial/mismatched
    activation" this way, rather than stopping at the first symptom.
    verified is exactly `not reasons`: "never mark a deployment
    successful when verification fails" holds by construction, not by a
    separate flag a caller could get out of sync with the reasons list.
    """

    def __init__(
        self,
        policy_service: LLMAgentPolicyService,
        template_service: LLMAgentPolicyTemplateService,
        instantiator: LLMAgentPolicyTemplateInstantiator,
        history_service: LLMAgentPolicyDeploymentHistory,
        version_service=None,
    ):
        self._policy_service = policy_service
        self._template_service = template_service
        self._instantiator = instantiator
        self._history_service = history_service
        self._version_service = version_service

    def verify(self, deployment_id: str, require_active: bool = True) -> VerificationResult:
        """
        require_active governs only the "is this policy currently
        ACTIVE" check: True (the default, and the only behavior this
        method had before Commit #10) is right for verifying a
        deployment that is supposed to still be the live one. Commit
        #10's own LLMAgentPolicyDeploymentRollbackService passes False
        when verifying a *rollback target* -- a deployment that was
        legitimately superseded (and therefore ARCHIVED) is not thereby
        an invalid one to roll back to; every other check (terminal
        state, rule validity, scope, template/version provenance) still
        runs exactly as before regardless of this flag.
        """
        reasons = []
        provenance = {}

        try:
            record = self._history_service.get(deployment_id)
        except UnknownDeploymentRecordError:
            return VerificationResult(
                deployment_id=deployment_id,
                reasons=[f"no deployment record was ever recorded for deployment_id {deployment_id!r}"],
            )

        provenance.update(
            intended_template_id=record.template_id,
            intended_template_version=record.template_version,
            intended_scope=record.target_scope,
            intended_policy_version=record.policy_version,
            recorded_status=record.status,
        )

        if record.status != DEPLOYMENT_SUCCEEDED:
            reasons.append(
                f"deployment did not reach the expected terminal state (recorded status: {record.status!r})"
            )
            return VerificationResult(
                deployment_id=deployment_id, policy_id=record.policy_id, verified=False,
                reasons=reasons, provenance=provenance,
            )

        try:
            policy = self._policy_service.get(record.policy_id)
        except UnknownAgentPolicyError:
            reasons.append(f"policy {record.policy_id!r} no longer exists")
            return VerificationResult(
                deployment_id=deployment_id, policy_id=record.policy_id, verified=False,
                reasons=reasons, provenance=provenance,
            )

        provenance["actual_scope"] = policy.scope_id
        provenance["policy_status"] = policy.status

        if require_active and policy.status != ACTIVE:
            reasons.append(f"policy {record.policy_id!r} is not ACTIVE (status: {policy.status!r})")

        if policy.scope_id != record.target_scope:
            reasons.append(
                f"policy {record.policy_id!r} is deployed in scope {policy.scope_id!r}, "
                f"expected {record.target_scope!r}"
            )

        try:
            LLMAgentPolicyService._validate_rules(policy.rules)
        except (InvalidAgentPolicyError, InvalidPolicyRuleError, DuplicateRuleIdError) as error:
            reasons.append(f"policy {record.policy_id!r} no longer has valid rules: {error}")

        actual_policy_version = None
        if self._version_service is not None:
            try:
                versions = self._version_service.list_versions(record.policy_id)
                actual_policy_version = versions[-1].version if versions else None
            except Exception:
                actual_policy_version = None
            provenance["actual_policy_version"] = actual_policy_version
            if record.policy_version is not None and actual_policy_version != record.policy_version:
                reasons.append(
                    f"policy {record.policy_id!r} is now at version {actual_policy_version!r}, "
                    f"expected the version deployed: {record.policy_version!r}"
                )

        actual_template_id = None
        actual_template_version = None
        try:
            instantiation_record = self._instantiator.provenance(record.policy_id)
            actual_template_id = instantiation_record.resolved_template_id
            actual_template_version = self._template_service.get(actual_template_id).version
        except (UnknownTemplateInstantiationPipelineError, UnknownPolicyTemplateError):
            pass

        provenance["actual_template_id"] = actual_template_id
        provenance["actual_template_version"] = actual_template_version

        if actual_template_id != record.template_id:
            reasons.append(
                f"policy {record.policy_id!r} is now traced to template {actual_template_id!r}, "
                f"expected {record.template_id!r}"
            )
        elif actual_template_version != record.template_version:
            reasons.append(
                f"template {record.template_id!r} is now at version {actual_template_version!r}, "
                f"expected the version deployed: {record.template_version!r}"
            )

        return VerificationResult(
            deployment_id=deployment_id, policy_id=record.policy_id, verified=not reasons,
            reasons=reasons, provenance=provenance,
        )
