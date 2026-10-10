from backend.agent_risk_profile import ARCHIVED, LLMAgentRiskProfileService
from backend.agent_risk_profile_activation import RiskProfileScopeMismatchError
from backend.agent_risk_profile_impact_analysis import LLMAgentRiskProfileImpactAnalyzer
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService

from .models import COMPATIBILITY_DRIFT, CONFIGURATION_DRIFT, NO_DRIFT, UNKNOWN, RiskProfileDriftResult


class LLMAgentRiskProfileDriftDetector:
    """Detects when a Commit #1 risk profile's live, active state no
    longer matches its own intended profile/version, supported actions,
    policies, or capabilities in its scope -- through the repository's
    real, existing comparison primitives, never a second risk evaluator.

    No dedicated drift-detection module exists anywhere in this
    repository for this domain (confirmed by inspection); the closest
    existing state-comparison precedent is
    backend.agent_policy_deployment_health.LLMAgentPolicyDeploymentHealthService's
    own "explicit UNKNOWN when there is not enough evidence, worst
    signal otherwise" discipline, mirrored here for the same reason:
    "do not infer drift from unavailable evidence".

    Not a second risk engine: every actual comparison is delegated
    entirely to Commit #9's own
    LLMAgentRiskProfileImpactAnalyzer.analyze(profile_id, version,
    scope_id) -- which already reuses Commit #1/#2's resolve_level(),
    Commit #5's compatibility check, and Commit #8's simulator to
    compare the profile's *current live state* against one specific
    version's own definition. This detector adds no new matching,
    scoring, or compatibility logic of its own:

      - CONFIGURATION_DRIFT is exactly "Commit #9's own
        risk_level_changes is non-empty" -- at least one action (or the
        bare default_level path) the live profile resolves differently
        than the expected version would, meaning the live rules/
        default_level have diverged from that recorded definition
        (e.g. a caller mutated the profile via
        LLMAgentRiskProfileService.update() directly, bypassing Commit
        #4's own create_version()/Commit #6's own activate()).
      - COMPATIBILITY_DRIFT is exactly "Commit #9's own
        blocking_conflicts is non-empty" while risk_level_changes is
        empty -- the profile's own rules still match the expected
        version exactly, but Commit #5's compatibility check no longer
        accepts that version for the current scope/target_context
        (Rule: "distinguish configuration drift from compatibility/
        environment drift").
      - affected_actions/affected_capabilities/affected_policies are
        Commit #9's own fields, copied verbatim.

    detect_version() lets a caller check against any specific
    historical version explicitly; detect() resolves "the intended
    version" as whatever Commit #4's own version history most recently
    recorded for profile_id -- the only notion of "authoritative
    expected version" this architecture actually has, never a second,
    independently-tracked "desired state" this repository cannot
    observe (Rule: "do not invent runtime or infrastructure state that
    the repository cannot actually observe").

    An ARCHIVED profile, or one with no recorded version at all, has no
    valid expected state to compare against (Rule: "archived profiles/
    versions must not be treated as valid expected state") -- both
    report drift_type UNKNOWN and drift_detected False, rather than a
    guessed NO_DRIFT/CONFIGURATION_DRIFT verdict built on evidence that
    does not exist.

    Zero side effects: this class holds no activation/version/rollout
    *store* reference of its own, only read-only service references, so
    there is nothing here capable of activating, deactivating, or
    rolling anything back (Rule: "No automatic repair, activation,
    deactivation, or rollback in this commit").
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        version_service: LLMAgentRiskProfileVersionService,
        impact_analyzer: LLMAgentRiskProfileImpactAnalyzer,
    ):
        self._profile_service = profile_service
        self._version_service = version_service
        self._impact_analyzer = impact_analyzer

    def detect(self, profile_id: str, scope_id: str, target_context: dict = None) -> RiskProfileDriftResult:
        """Detect drift between profile_id's live state and whichever
        version Commit #4's own version history most recently recorded
        for it -- "the intended profile/version" this architecture
        actually has a record of.

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

        if profile.status == ARCHIVED:
            return self._unknown_result(
                profile_id, scope_id, expected_version=None, actual_version=profile.version,
                details=["profile is archived; archived profiles are not treated as valid expected state"],
            )

        versions = self._version_service.list_versions(profile_id)
        if not versions:
            return self._unknown_result(
                profile_id, scope_id, expected_version=None, actual_version=profile.version,
                details=["no recorded version exists for this profile; there is no authoritative baseline "
                         "to compare against"],
            )

        return self.detect_version(profile_id, versions[-1].version, scope_id, target_context=target_context)

    def detect_version(
        self, profile_id: str, version: int, scope_id: str, target_context: dict = None
    ) -> RiskProfileDriftResult:
        """Detect drift between profile_id's live state and one
        specific, explicitly-named version.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            RiskProfileScopeMismatchError: If scope_id does not match
                profile_id's own scope_id
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record (propagated unchanged from Commit #4's
                own get_version())
        """
        profile = self._profile_service.get(profile_id)
        if profile.scope_id != scope_id:
            raise RiskProfileScopeMismatchError(
                f"profile {profile_id!r} belongs to scope {profile.scope_id!r}, not {scope_id!r}"
            )

        if profile.status == ARCHIVED:
            return self._unknown_result(
                profile_id, scope_id, expected_version=version, actual_version=profile.version,
                details=["profile is archived; archived profiles are not treated as valid expected state"],
            )

        # Raises UnknownRiskProfileVersionError unchanged if version was
        # never recorded -- confirms it exists before analyze() is asked
        # to compare against it.
        self._version_service.get_version(profile_id, version)

        impact = self._impact_analyzer.analyze(profile_id, version, scope_id, target_context=target_context)

        configuration_drift = bool(impact.risk_level_changes)
        compatibility_drift = bool(impact.blocking_conflicts)

        if configuration_drift:
            drift_type = CONFIGURATION_DRIFT
        elif compatibility_drift:
            drift_type = COMPATIBILITY_DRIFT
        else:
            drift_type = NO_DRIFT

        details = []
        if profile.version != version:
            details.append(
                f"expected version {version} does not match the profile's current live version {profile.version}"
            )
        for change in impact.risk_level_changes:
            details.append(
                f"action {change['action']!r} currently resolves to {change['before']!r} live, but expected "
                f"version {version} defines {change['after']!r}"
            )
        details.extend(impact.blocking_conflicts)

        return RiskProfileDriftResult(
            profile_id=profile_id,
            scope_id=scope_id,
            expected_version=version,
            actual_version=profile.version,
            drift_detected=configuration_drift or compatibility_drift,
            drift_type=drift_type,
            affected_actions=impact.affected_actions,
            affected_capabilities=impact.affected_capabilities,
            affected_policies=impact.affected_policies,
            details=details,
            provenance={"impact_analysis": impact.to_dict()},
        )

    @staticmethod
    def _unknown_result(profile_id, scope_id, expected_version, actual_version, details) -> RiskProfileDriftResult:
        return RiskProfileDriftResult(
            profile_id=profile_id,
            scope_id=scope_id,
            expected_version=expected_version,
            actual_version=actual_version,
            drift_detected=False,
            drift_type=UNKNOWN,
            affected_actions=[],
            affected_capabilities=[],
            affected_policies=[],
            details=details,
            provenance={},
        )
