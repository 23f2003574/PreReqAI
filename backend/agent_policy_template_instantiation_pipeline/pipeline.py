from backend.agent_policy_engine import LLMAgentPolicy
from backend.agent_policy_template_compatibility import LLMAgentPolicyTemplateCompatibility
from backend.agent_policy_template_migration import LLMAgentPolicyTemplateMigrator
from backend.agent_policy_template_validation import LLMAgentPolicyTemplateValidator
from backend.agent_policy_templates import ARCHIVED, ArchivedPolicyTemplateError, LLMAgentPolicyTemplateService

from .models import TemplateInstantiationPipelineRecord


class TemplateInstantiationValidationError(ValueError):
    """Raised when Commit #3's own validator finds the requested
    template, or the given parameters, invalid -- before anything is
    migrated, compatibility-checked, or persisted."""


class TemplateInstantiationCompatibilityError(ValueError):
    """Raised when Commit #4's own compatibility check finds the
    (resolved) template incompatible with the target scope -- before
    anything is persisted."""


class UnknownTemplateInstantiationPipelineError(KeyError):
    """Raised when provenance() is given a policy_id this pipeline's own
    instantiate() never produced."""


class LLMAgentPolicyTemplateInstantiator:
    """The single pipeline that turns a validated, compatible Commit #1
    policy template into a fully materialized, persisted LLMAgentPolicy
    -- composing Commits #1-#5, never reimplementing any of them, the
    same pure-composition-root shape the base agent_policy_* series'
    own Commit #13 LLMAgentPolicyGovernanceOrchestrator already
    established for that series.

    instantiate() runs exactly this pipeline, in this order, and no more:

        load template
            Commit #1's own LLMAgentPolicyTemplateService.get() --
            UnknownPolicyTemplateError propagates unchanged. An ARCHIVED
            template is rejected immediately here (Commit #1's own
            ArchivedPolicyTemplateError, reused rather than a second
            error type), before any of the more expensive checks below
            ever run.
        validate parameters/template
            Commit #3's own LLMAgentPolicyTemplateValidator.validate()
            (structure) and .validate_parameters() (the given
            parameters) -- any issue raises
            TemplateInstantiationValidationError before migration,
            compatibility, or persistence are ever attempted.
        migrate if an explicit target version is requested
            Commit #5's own LLMAgentPolicyTemplateMigrator.migrate(),
            called only when target_version is not None -- its own
            UnsupportedTemplateMigrationError/InvalidMigratedTemplateError
            propagate unchanged. The template actually used for every
            following step becomes the migrated one; the originally
            requested template_id is still preserved in this pipeline's
            own TemplateInstantiationPipelineRecord. Parameters are
            re-validated against the migrated template's own
            (potentially different) placeholders, since a migration is,
            in general, free to change them.
        check compatibility
            Commit #4's own LLMAgentPolicyTemplateCompatibility.check(),
            given {"scope_id": scope_id} merged with any caller-supplied
            target_context -- an incompatible result raises
            TemplateInstantiationCompatibilityError before persistence.
        materialize policy / validate policy / persist through existing
        policy service
            All three of these are exactly one call to Commit #1's own
            LLMAgentPolicyTemplateService.instantiate() -- parameter
            substitution, Commit #1 (base series)'s own rule validation,
            and the actual persistence are all already that method's own
            job, verbatim, never duplicated here. Since this is the only
            write in the whole pipeline, and it happens strictly last
            (after every earlier gate already passed), a failure at any
            earlier stage -- or a failure raised from inside this call
            itself -- leaves nothing partially persisted: either this
            one call fully succeeds and returns a real LLMAgentPolicy,
            or nothing was ever written.

    A version_service (Commit #11, base series) may optionally be given:
    when it is, this pipeline's own provenance record additionally
    carries the freshly created policy's current_version, read via
    version_service.list_versions() -- a pure, read-only confirmation
    that reuses Commit #11's own versioning rather than computing
    anything about "version 1" independently. This requires nothing
    special of template_service's own construction: Commit #1's
    LLMAgentPolicyTemplateService already accepts any policy_service
    (a bare LLMAgentPolicyService, or a Commit #10
    LLMAgentPolicyHistoryTrackedService) duck-typed, so a caller who
    wants every instantiated policy's creation tracked simply builds
    template_service with a tracked policy_service to begin with -- this
    pipeline neither requires nor prevents that, and never constructs
    its own policy_service internally.

    Never mutates the source template: no step above ever calls
    template_service.update()/archive() on it. Parameter substitution is
    exactly Commit #1's own deterministic str.format()-based substitution
    (LLMAgentPolicyTemplateService.instantiate() itself) -- the same
    parameters always produce the same materialized rules.
    """

    def __init__(
        self,
        template_service: LLMAgentPolicyTemplateService,
        validator: LLMAgentPolicyTemplateValidator = None,
        compatibility: LLMAgentPolicyTemplateCompatibility = None,
        migrator: LLMAgentPolicyTemplateMigrator = None,
        version_service=None,
    ):
        self._template_service = template_service
        self._validator = validator if validator is not None else LLMAgentPolicyTemplateValidator()
        self._compatibility = (
            compatibility if compatibility is not None else LLMAgentPolicyTemplateCompatibility(self._validator)
        )
        self._migrator = (
            migrator
            if migrator is not None
            else LLMAgentPolicyTemplateMigrator(template_service, self._validator, self._compatibility)
        )
        self._version_service = version_service
        self._records_by_policy_id: dict[str, TemplateInstantiationPipelineRecord] = {}

    def instantiate(
        self,
        template_id: str,
        scope_id: str,
        parameters: dict,
        target_version: int = None,
        target_context: dict = None,
    ) -> LLMAgentPolicy:
        """Run the full load -> validate -> migrate -> compatibility ->
        materialize/validate/persist pipeline for template_id, returning
        the resulting, fully persisted LLMAgentPolicy.

        Raises:
            UnknownPolicyTemplateError: If template_id was never created
                (propagated from Commit #1's own get(), not wrapped)
            ArchivedPolicyTemplateError: If the template is ARCHIVED
            TemplateInstantiationValidationError: If Commit #3's own
                validator finds the template or parameters invalid
            UnsupportedTemplateMigrationError, InvalidMigratedTemplateError:
                Propagated unchanged from Commit #5's migrate(), when
                target_version is given
            TemplateInstantiationCompatibilityError: If Commit #4's own
                compatibility check finds the resolved template
                incompatible with scope_id
            InvalidAgentPolicyError, InvalidPolicyRuleError,
                DuplicateRuleIdError, MissingTemplateParameterError,
                UnexpectedTemplateParameterError: Propagated unchanged
                from Commit #1's own instantiate(), should this pipeline's
                own validation somehow miss something it catches
        """
        template = self._template_service.get(template_id)
        if template.status == ARCHIVED:
            raise ArchivedPolicyTemplateError(f"template {template_id!r} is archived and cannot be instantiated")

        self._require_valid(self._validator.validate(template), "template")
        self._require_valid(self._validator.validate_parameters(template, parameters), "parameters")

        resolved_template = template
        migrated = False
        if target_version is not None:
            resolved_template = self._migrator.migrate(template, target_version)
            migrated = True
            self._require_valid(
                self._validator.validate_parameters(resolved_template, parameters), "parameters (post-migration)"
            )

        context = {"scope_id": scope_id}
        if target_context:
            context.update(target_context)
        compatibility_result = self._compatibility.check(resolved_template, context)
        if not compatibility_result.compatible:
            raise TemplateInstantiationCompatibilityError(
                f"template {resolved_template.template_id!r} is not compatible with scope {scope_id!r}: "
                f"{'; '.join(compatibility_result.reasons)}"
            )

        policy = self._template_service.instantiate(resolved_template.template_id, scope_id, parameters)

        current_version = self._current_version(policy.policy_id)

        record = TemplateInstantiationPipelineRecord(
            requested_template_id=template_id,
            resolved_template_id=resolved_template.template_id,
            target_version=target_version,
            migrated=migrated,
            scope_id=scope_id,
            policy_id=policy.policy_id,
            parameters=dict(parameters) if isinstance(parameters, dict) else parameters,
            current_version=current_version,
        )
        self._records_by_policy_id[policy.policy_id] = record

        return policy

    def provenance(self, policy_id: str) -> TemplateInstantiationPipelineRecord:
        """The TemplateInstantiationPipelineRecord for policy_id.

        Raises:
            UnknownTemplateInstantiationPipelineError: If policy_id was
                never produced by this pipeline's own instantiate()
        """
        record = self._records_by_policy_id.get(policy_id)
        if record is None:
            raise UnknownTemplateInstantiationPipelineError(policy_id)
        return record

    def _current_version(self, policy_id: str):
        if self._version_service is None:
            return None
        versions = self._version_service.list_versions(policy_id)
        return versions[-1].version if versions else None

    @staticmethod
    def _require_valid(validation_result, what: str) -> None:
        if not validation_result.is_valid:
            details = "; ".join(
                f"{issue.code}: {issue.message}" + (f" ({issue.path})" if issue.path else "")
                for issue in validation_result.issues
            )
            raise TemplateInstantiationValidationError(f"invalid {what}: {details}")
