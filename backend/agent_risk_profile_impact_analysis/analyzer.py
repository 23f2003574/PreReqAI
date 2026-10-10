from backend.agent_policy_engine import ACTIVE as POLICY_ACTIVE
from backend.agent_policy_engine import LLMAgentPolicyService
from backend.agent_risk_profile import LLMAgentRiskProfileService, resolve_level
from backend.agent_risk_profile_activation import RiskProfileScopeMismatchError
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility

# Commit #5's own capability-introspection helper, reused verbatim
# rather than a second implementation -- the same "reach into a
# sibling module's own private helper rather than duplicate its logic"
# precedent backend.agent_policy_template_validation already
# established for backend.agent_policy_templates.service._placeholders_in.
from backend.agent_risk_profile_compatibility.compatibility import _match_fields_used
from backend.agent_risk_profile_simulation import LLMAgentRiskProfileSimulator
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, profile_from_version
from backend.llm.tools import LLMToolRegistryService, UnknownToolError

from .models import RiskProfileImpactResult


class InvalidRiskProfileImpactAnalysisError(ValueError):
    """Raised when analyze() is given a blank/invalid target_scope."""


def _referenced_tool_names(*profiles) -> list:
    """Every distinct tool_name value actually named by an exact
    equality match constraint across the given profiles' own
    action_rules -- the only kind of match value that names one
    concrete action unambiguously (a list/tuple/set of acceptable
    values, or no tool_name constraint at all, names no single action
    and is never guessed into one)."""
    names = set()
    for profile in profiles:
        for rule in profile.action_rules:
            tool_name = rule.match.get("tool_name")
            if isinstance(tool_name, str):
                names.add(tool_name)
    return sorted(names)


class LLMAgentRiskProfileImpactAnalyzer:
    """Deterministically previews what activating or changing one
    Commit #1 risk profile's version could affect, before that version
    is ever actually activated (Commit #6) or the profile itself is
    changed.

    Not a second risk, dependency, or graph engine: every affected-*
    list is derived from an actual, already-existing repository
    relationship, and every risk/compatibility judgment is delegated
    entirely to collaborators this whole series already ships --

      - the target version's own content comes from Commit #4's
        LLMAgentRiskProfileVersionService.get_version(), reconstructed
        into a real, in-memory (never persisted)
        LLMAgentRiskProfile via Commit #6's own profile_from_version()
      - "would this even be compatible" is Commit #5's own
        LLMAgentRiskProfileCompatibility.check() -- the exact same gate
        Commit #6's own activate() already runs before mutating
        anything, run here read-only
      - "would this change a given action's risk level, and what
        conflicts would surface" is Commit #8's own
        LLMAgentRiskProfileSimulator.simulate() and Commit #1/#2's own
        resolve_level() -- never a second scoring or matching pass
      - "which real policies/tools does this scope actually have" is
        backend.agent_policy_engine.LLMAgentPolicyService.list()/
        backend.llm.tools.LLMToolRegistryService.get(), both optional
        collaborators that degrade to an empty, honest answer rather
        than a fabricated one when not configured (Rule: "If the
        repository has no existing relationship for a category, do not
        fabricate one")

    analyze() never mutates, persists, activates, or deploys anything --
    it holds no profile/version/activation *store* of its own, only
    read-only service references, so there is nothing here capable of
    changing current state even by mistake.
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        policy_service: LLMAgentPolicyService = None,
        tool_registry: LLMToolRegistryService = None,
        compatibility: LLMAgentRiskProfileCompatibility = None,
        simulator: LLMAgentRiskProfileSimulator = None,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._policy_service = policy_service
        self._tool_registry = tool_registry
        self._compatibility = compatibility if compatibility is not None else LLMAgentRiskProfileCompatibility()
        self._simulator = simulator if simulator is not None else LLMAgentRiskProfileSimulator()

    def analyze(
        self, profile_id: str, version: int, target_scope: str, target_context: dict = None
    ) -> RiskProfileImpactResult:
        """Analyze the impact of profile_id's version `version` for
        target_scope -- whether that version is the profile's own
        current, already-active state, or a specific historical/
        not-yet-activated one.

        target_context, when given, is folded into Commit #5's own
        compatibility check (with "scope_id" defaulted to target_scope)
        -- a caller who wants to check further runtime capabilities
        (supported_match_fields, supported_tiers, ...) may supply them
        here, the same optional-richer-context shape Commit #6's own
        activate() already accepts.

        Raises:
            InvalidRiskProfileImpactAnalysisError: If target_scope is
                missing
            UnknownRiskProfileError: If profile_id was never created
                (propagated unchanged from Commit #1's own get())
            RiskProfileScopeMismatchError: If target_scope does not
                match profile_id's own scope_id
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record (propagated unchanged from Commit #4's
                own get_version())
        """
        if not target_scope or not isinstance(target_scope, str):
            raise InvalidRiskProfileImpactAnalysisError(
                "target_scope is required and must identify a project/notebook/API"
            )

        profile = self._profile_service.get(profile_id)
        if profile.scope_id != target_scope:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {target_scope!r}"
            )

        target_version = self._version_service.get_version(profile_id, version)
        prospective = profile_from_version(profile, target_version)

        affected_actions = self._affected_actions(profile, prospective)
        affected_capabilities = sorted(_match_fields_used(prospective))
        affected_policies = self._affected_policies(target_scope)
        affected_scopes = [target_scope]

        risk_level_changes = []
        warnings = []
        for action_context in [{"tool_name": name} for name in affected_actions] + [{}]:
            before_level, _, _ = resolve_level(profile, action_context)
            simulated = self._simulator.simulate(prospective, action_context)
            if before_level != simulated.risk_level:
                risk_level_changes.append(
                    {
                        "action": action_context.get("tool_name"),
                        "before": before_level,
                        "after": simulated.risk_level,
                    }
                )
            warnings.extend(simulated.conflicts)

        context = dict(target_context) if target_context is not None else {}
        context.setdefault("scope_id", target_scope)
        compatibility_result = self._compatibility.check(prospective, context)
        blocking_conflicts = [] if compatibility_result.compatible else list(compatibility_result.reasons)

        impact_summary = (
            f"{len(risk_level_changes)} risk level change(s) across {len(affected_actions)} affected "
            f"action(s); {len(blocking_conflicts)} blocking conflict(s); {len(warnings)} warning(s)"
        )

        return RiskProfileImpactResult(
            profile_id=profile_id,
            version=version,
            target_scope=target_scope,
            affected_actions=affected_actions,
            affected_capabilities=affected_capabilities,
            affected_policies=affected_policies,
            affected_scopes=affected_scopes,
            risk_level_changes=risk_level_changes,
            blocking_conflicts=blocking_conflicts,
            warnings=warnings,
            impact_summary=impact_summary,
            provenance={
                "profile": profile,
                "target_version": target_version.to_dict(),
                "compatibility": compatibility_result.to_dict(),
            },
        )

    def _affected_actions(self, profile, prospective) -> list:
        candidates = _referenced_tool_names(profile, prospective)
        if self._tool_registry is None:
            return candidates

        registered = []
        for tool_name in candidates:
            try:
                self._tool_registry.get(tool_name)
            except UnknownToolError:
                continue
            registered.append(tool_name)
        return registered

    def _affected_policies(self, target_scope: str) -> list:
        if self._policy_service is None:
            return []
        return [policy.policy_id for policy in self._policy_service.list(target_scope, status=POLICY_ACTIVE)]
