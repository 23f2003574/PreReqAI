from backend.agent_risk_profile import (
    ACTIVE,
    ARCHIVED,
    InvalidRiskProfileError,
    LLMAgentRiskProfile,
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
)
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, profile_from_version

from .models import ACTIVATED, ALREADY_ACTIVE, ActivationResult


class RiskProfileScopeMismatchError(ValueError):
    """Raised when activate()/deactivate() is given a scope_id that does
    not match profile_id's own scope_id (Commit #1's own scope
    isolation, enforced here too rather than re-derived)."""


class ArchivedRiskProfileCannotActivateError(ValueError):
    """Raised when activate() is given a profile_id that is ARCHIVED.

    An archived profile is retired, per Commit #1's own semantics
    (Rule: "Archived profiles cannot activate") -- reviving one
    requires a fresh LLMAgentRiskProfileService.create() call, never an
    activation.
    """


class IncompatibleRiskProfileVersionError(ValueError):
    """Raised when the requested version fails Commit #5's own
    compatibility check (which itself composes Commit #3's validator)
    against the activation target -- nothing is mutated, and whatever
    version the profile was previously live with is left exactly as it
    was (Rule: "Failed activation leaves the previous active version
    unchanged")."""


class LLMAgentRiskProfileActivationService:
    """Safely activates one immutable Commit #4 risk profile version for
    a scope, and makes it the one Commit #2's
    LLMAgentRiskProfileResolver actually resolves with -- through the
    repository's real, existing activation mechanism, never a second
    configuration/state framework.

    Holds no state of its own: there is no separate "is this profile
    active for this scope" ledger anywhere in this class, because one
    already exists -- Commit #1's own ACTIVE/ARCHIVED
    LLMAgentRiskProfile.status *is* the real activation mechanism (a
    profile the resolver ever considers is, by definition, ACTIVE), and
    Commit #1's own live action_rules/default_level *is* what "the
    version currently used by profile resolution" already means, since
    the resolver always reads the live profile, never a separately
    tracked pointer. This mirrors
    backend.agent_policy_template_deployment.LLMAgentPolicyTemplateDeploymentService's
    own central insight for an analogous problem one series over:
    "there is no separate draft/staged status... activate through
    existing policy mechanism is exactly Commit #1's own archive()"
    -- adapted here to risk profiles, whose Commit #1 already carries a
    version counter the base series' own LLMAgentPolicy never had, so
    there is even less new bookkeeping needed than that precedent
    required.

    activate() runs exactly the goal's own flow, and no more:

        validate -> compatibility check
            A single call to Commit #5's own
            LLMAgentRiskProfileCompatibility.check() against a purely
            in-memory *prospective* profile (never persisted) built
            from the requested version's own frozen definition --
            Commit #5's own check() already composes Commit #3's
            validator as its own final step once every dedicated
            compatibility concern passes, so there is no separate
            validate() call to make here; doing so would just be a
            second copy of exactly what check() already runs. Nothing
            is mutated before this call returns compatible.
        activate version
            Only once compatible: Commit #4's own
            LLMAgentRiskProfileVersionService.create_version() is
            called with the requested version's own name/action_rules/
            default_level -- the exact same, unmodified mutation route
            every other caller of Commit #1's update() already goes
            through (no parallel mutation path), and the exact same
            "record a new version only when profile.version actually
            advances" guarantee Commit #4 already provides. Restoring
            an older version's content onto a profile that has since
            moved on therefore never rewrites that older version's own
            immutable record (Rule: "Never mutate immutable versions")
            -- it mints a new version number carrying the restored
            content forward, which is exactly what "activate" a past
            version safely means for an immutable history.
        record provenance
            The resulting ActivationResult embeds both the requested
            LLMAgentRiskProfileVersion and the one Commit #4 actually
            produced (Rule: "Preserve activation provenance") --
            these differ exactly in the "restoring an old version"
            case described above, and are identical (down to
            version_id) whenever the requested version was already
            current.

    Because the compatibility gate runs strictly before create_version()
    is ever called, any IncompatibleRiskProfileVersionError leaves the
    profile's live action_rules/default_level/version completely
    untouched -- "failed activation leaves the previous active version
    unchanged" holds structurally, not by a separate rollback step.

    deactivate() is exactly Commit #1's own
    LLMAgentRiskProfileService.archive() -- the same real mechanism that
    already makes a profile unresolvable (Commit #1/#2's own
    ARCHIVED-profiles-excluded guarantee), scope-checked first so a
    caller can never deactivate a profile belonging to another scope.

    get_active() reads Commit #1's own live state directly: the scope's
    current ACTIVE scope-default profile (action_name and
    action_category both None -- the same narrowing Commit #1's own
    LLMAgentRiskProfileService.resolve() already applies, since a scope
    may otherwise have several simultaneously-ACTIVE, differently-tiered
    profiles per Commit #2) paired with Commit #4's own version record
    for its current, live version number.
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        compatibility: LLMAgentRiskProfileCompatibility = None,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._compatibility = compatibility if compatibility is not None else LLMAgentRiskProfileCompatibility()

    def activate(
        self,
        profile_id: str,
        version: int,
        scope_id: str,
        target_context: dict = None,
        actor: str = None,
        reason: str = None,
    ) -> ActivationResult:
        """Activate profile_id's version `version` for scope_id.

        target_context is passed through to Commit #5's own
        compatibility check, with "scope_id" defaulted to scope_id when
        not otherwise supplied -- a caller who wants to check further
        runtime capabilities (supported_risk_levels, supported_tiers,
        ...) may supply them here.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
                (propagated unchanged from Commit #1's own get())
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
            ArchivedRiskProfileCannotActivateError: If profile_id is
                ARCHIVED
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record (propagated unchanged from Commit #4's
                own get_version())
            IncompatibleRiskProfileVersionError: If Commit #5's own
                compatibility check finds the requested version
                incompatible with target_context
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )
        if profile.status == ARCHIVED:
            raise ArchivedRiskProfileCannotActivateError(
                f"profile {profile_id!r} is archived and cannot be activated"
            )

        target_version = self._version_service.get_version(profile_id, version)

        prospective = profile_from_version(profile, target_version)
        context = dict(target_context) if target_context is not None else {}
        context.setdefault("scope_id", scope_id)
        compatibility_result = self._compatibility.check(prospective, context)
        if not compatibility_result.compatible:
            raise IncompatibleRiskProfileVersionError(
                f"profile {profile_id!r} version {version} cannot be activated for scope {scope_id!r}: "
                f"{'; '.join(compatibility_result.reasons)}"
            )

        before_version = profile.version
        definition = target_version.definition
        resulting_version = self._version_service.create_version(
            profile_id,
            name=definition["name"],
            action_rules=[RiskProfileActionRule.from_dict(rule) for rule in definition["action_rules"]],
            default_level=definition["default_level"],
            actor=actor,
            reason=reason if reason is not None else f"activated from version {version}",
        )

        status = ACTIVATED if resulting_version.version != before_version else ALREADY_ACTIVE

        return ActivationResult(
            profile_id=profile_id,
            scope_id=scope_id,
            requested_version=version,
            version=resulting_version.version,
            previous_version=before_version,
            status=status,
            provenance={
                "requested_version": target_version.to_dict(),
                "resulting_version": resulting_version.to_dict(),
                "compatibility": compatibility_result.to_dict(),
                "actor": actor,
                "reason": reason,
            },
        )

    def deactivate(self, profile_id: str, scope_id: str) -> LLMAgentRiskProfile:
        """Deactivate profile_id: the real, existing mechanism (Commit
        #1's own archive()) that makes it unresolvable by Commit #2's
        own resolver from this point on. Idempotent, exactly as
        archive() itself already is.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )

        return self._profile_service.archive(profile_id)

    def get_active(self, scope_id: str):
        """The (profile, version) pair currently used by profile
        resolution for scope_id's scope-default profile, or None when
        scope_id has no ACTIVE scope-default profile at all -- the
        exact same narrowing Commit #1's own
        LLMAgentRiskProfileService.resolve() already applies.

        Raises:
            InvalidRiskProfileError: If scope_id is missing
            UnknownRiskProfileVersionError: If the profile's own live
                version was never recorded via
                LLMAgentRiskProfileVersionService.create_version() --
                propagated unchanged, never silently synthesized
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskProfileError("scope_id is required and must identify a project/notebook/API")

        defaults = [
            profile
            for profile in self._profile_service.list(scope_id, status=ACTIVE)
            if profile.action_name is None and profile.action_category is None
        ]
        if not defaults:
            return None

        profile = defaults[0]
        version = self._version_service.get_version(profile.profile_id, profile.version)
        return profile, version
