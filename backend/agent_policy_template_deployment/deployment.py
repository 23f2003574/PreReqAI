from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from backend.agent_policy_engine import ARCHIVED, LLMAgentPolicyService
from backend.agent_policy_template_compatibility import LLMAgentPolicyTemplateCompatibility
from backend.agent_policy_template_instantiation_pipeline import (
    LLMAgentPolicyTemplateInstantiator,
    UnknownTemplateInstantiationPipelineError,
)
from backend.agent_policy_templates import LLMAgentPolicyTemplateService

from .models import ALREADY_DEPLOYED, DEPLOYED, DeploymentResult


class InvalidDeploymentPolicyError(ValueError):
    """Raised when deploy() is given a policy_id that is ARCHIVED, or
    that was never produced by Commit #6's own instantiation pipeline --
    without that pipeline's provenance there is no template to run
    Commit #4's compatibility check against, and this service never
    guesses one."""


class DeploymentCompatibilityError(ValueError):
    """Raised when Commit #4's own compatibility check finds the
    policy's resolved template incompatible with target_context -- the
    policy is never activated and nothing about the previously deployed
    policy changes."""


class UnknownDeploymentError(KeyError):
    """Raised when provenance() is given a policy_id this service's own
    deploy() never recorded a DeploymentResult for."""


class LLMAgentPolicyTemplateDeploymentService:
    """Deploys an already-instantiated Commit #1 LLMAgentPolicy (one
    produced by Commit #6's own LLMAgentPolicyTemplateInstantiator)
    through the repository's real, existing policy activation mechanism
    -- Commit #1 (base series)'s own ACTIVE/ARCHIVED status -- never a
    second deployment/activation framework.

    There is no separate "draft" or "staged" status anywhere in this
    repository: a Commit #1 policy is already ACTIVE, and therefore
    already resolvable by backend.agent_policy_resolution.LLMAgentPolicyResolver,
    from the moment LLMAgentPolicyService.create() persists it.
    "Activate through existing policy mechanism" is therefore exactly
    Commit #1's own archive() applied to whichever policy this service
    is REPLACING, never a new activation call on the incoming policy
    itself (which is already active, or otherwise rejected outright --
    see deploy()'s own "validate policy" step). This service's genuine
    value-add is bookkeeping: which policy_id is currently the deployed
    one for a given (scope_id, template name) pair, so a later
    deployment of the same template family into the same scope knows
    what it is superseding, without this service inventing a new
    "current version" concept LLMAgentPolicy itself has no notion of.

    deploy() runs exactly this flow, and no more:

        validate policy
            Commit #1's own LLMAgentPolicyService.get() (its own
            UnknownAgentPolicyError propagates unchanged) plus one
            additional check this service adds: policy_id must not be
            ARCHIVED, and must have real Commit #6 instantiation
            provenance (InvalidDeploymentPolicyError otherwise) -- a
            policy this service cannot trace back to a template is one
            it can never compatibility-check, so it is never deployed.
        verify target compatibility
            Commit #4's own LLMAgentPolicyTemplateCompatibility.check(),
            run against the exact template Commit #6's provenance says
            produced this policy -- DeploymentCompatibilityError on any
            incompatibility, before anything else changes.
        create deployment/version record
        → activate through existing policy mechanism
        → record template/version provenance
            All three happen together, in this exact order, only once
            the two gates above already passed: this service's own
            (scope_id, template name) -> policy_id pointer is read to
            find whatever policy_id it currently points to (None on a
            first deployment); if that differs from the incoming
            policy_id, Commit #1's own archive() is called on it --
            the "activation" step, and the ONLY mutation this method
            ever performs on an existing policy -- and only after that
            succeeds does this service's own pointer move to the new
            policy_id and a DeploymentResult get recorded. Because the
            previous policy is archived (not the new one activated --
            it already was) strictly after compatibility already
            passed, and the pointer/record are only written after
            archive() itself already succeeded, "preserve the previous
            active policy until the new one is successfully activated"
            and "failed deployment leaves the active policy unchanged"
            both hold structurally: any exception raised by archive()
            itself leaves the previous policy exactly as ACTIVE as it
            was, and this service's own pointer/record untouched.

    Repeated deploy() calls for a policy_id that is already the current
    one for its (scope_id, template name) pair are idempotent: no
    archive() call is repeated, no new DeploymentResult is recorded --
    the original one is simply returned again, with status
    ALREADY_DEPLOYED.

    Scope-isolated by construction: the (scope_id, template name) key
    this service tracks its own "currently deployed" pointer under means
    a deployment to one scope can never read, let alone archive, a
    policy belonging to any other scope -- exactly Commit #1 (base
    series)'s own scope isolation, never re-derived independently here.
    """

    def __init__(
        self,
        policy_service: LLMAgentPolicyService,
        template_service: LLMAgentPolicyTemplateService,
        instantiator: LLMAgentPolicyTemplateInstantiator,
        compatibility: LLMAgentPolicyTemplateCompatibility = None,
    ):
        self._policy_service = policy_service
        self._template_service = template_service
        self._instantiator = instantiator
        self._compatibility = compatibility if compatibility is not None else LLMAgentPolicyTemplateCompatibility()
        self._current_by_key: dict[tuple, str] = {}
        self._deployments_by_policy_id: dict[str, DeploymentResult] = {}

    def deploy(self, policy_id: str, target_context: dict) -> DeploymentResult:
        """Deploy policy_id, replacing whatever policy previously
        occupied its (scope, template family) slot.

        Raises:
            UnknownAgentPolicyError: If policy_id was never created
                (propagated from Commit #1's own get(), not wrapped)
            InvalidDeploymentPolicyError: If policy_id is ARCHIVED, or
                was never produced by Commit #6's instantiation pipeline
            DeploymentCompatibilityError: If Commit #4's own
                compatibility check finds the policy's template
                incompatible with target_context
        """
        policy = self._policy_service.get(policy_id)
        if policy.status == ARCHIVED:
            raise InvalidDeploymentPolicyError(f"policy {policy_id!r} is archived and cannot be deployed")

        try:
            instantiation_record = self._instantiator.provenance(policy_id)
        except UnknownTemplateInstantiationPipelineError as error:
            raise InvalidDeploymentPolicyError(
                f"policy {policy_id!r} has no known template provenance -- it must be produced by "
                f"Commit #6's own LLMAgentPolicyTemplateInstantiator before it can be deployed"
            ) from error

        template = self._template_service.get(instantiation_record.resolved_template_id)

        compatibility_result = self._compatibility.check(template, target_context)
        if not compatibility_result.compatible:
            raise DeploymentCompatibilityError(
                f"policy {policy_id!r}'s template {template.template_id!r} is not compatible with "
                f"the deployment target: {'; '.join(compatibility_result.reasons)}"
            )

        key = (policy.scope_id, template.name)
        current_policy_id = self._current_by_key.get(key)

        if current_policy_id == policy_id:
            existing = self._deployments_by_policy_id.get(policy_id)
            if existing is not None:
                # this exact call is a no-op replay -- the canonical
                # record kept for provenance() is left as DEPLOYED
                # (it genuinely is), but this call's own return value
                # says so explicitly, with the original deployment_id/
                # deployed_at preserved unchanged
                return replace(existing, status=ALREADY_DEPLOYED)

        previous_policy_id = current_policy_id if current_policy_id != policy_id else None
        if previous_policy_id is not None:
            self._policy_service.archive(previous_policy_id)

        self._current_by_key[key] = policy_id

        result = DeploymentResult(
            deployment_id=str(uuid4()),
            policy_id=policy_id,
            scope_id=policy.scope_id,
            template_id=template.template_id,
            template_version=template.version,
            status=DEPLOYED,
            previous_policy_id=previous_policy_id,
            deployed_at=datetime.now(timezone.utc),
        )
        self._deployments_by_policy_id[policy_id] = result
        return result

    def provenance(self, policy_id: str) -> DeploymentResult:
        """The DeploymentResult recorded for policy_id.

        Raises:
            UnknownDeploymentError: If policy_id was never deployed by
                this service's own deploy()
        """
        result = self._deployments_by_policy_id.get(policy_id)
        if result is None:
            raise UnknownDeploymentError(policy_id)
        return result

    def current_for(self, scope_id: str, template_name: str):
        """The policy_id currently deployed for (scope_id, template_name),
        or None if nothing has ever been deployed for it."""
        return self._current_by_key.get((scope_id, template_name))
