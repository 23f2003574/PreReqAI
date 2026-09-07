from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Distinguishes *what kind* of divergence detect()/detect_version()
# found -- mirrors backend.agent_policy_deployment_health's own
# "explicit UNKNOWN when there is not enough evidence to say anything
# else" discipline (this repository's closest existing state-comparison
# precedent), rather than collapsing every kind of divergence into one
# generic boolean. CONFIGURATION_DRIFT means the profile's own live
# rules/default_level no longer match what the expected version defines
# (Commit #1/#9's own resolve_level() disagrees for at least one
# action); COMPATIBILITY_DRIFT means the rules still match, but Commit
# #5's own compatibility check now finds the expected version
# incompatible with the current scope/target_context (the environment
# moved, not the profile's own content); UNKNOWN is the answer whenever
# there is no valid expected state to compare against at all (an
# ARCHIVED profile, or a profile with no recorded version yet) --
# "archived profiles/versions must not be treated as valid expected
# state" and "do not fabricate undetectable external state" both hold
# by having this explicit escape hatch rather than defaulting to
# NO_DRIFT or CONFIGURATION_DRIFT out of a lack of evidence.
NO_DRIFT = "no_drift"
CONFIGURATION_DRIFT = "configuration_drift"
COMPATIBILITY_DRIFT = "compatibility_drift"
UNKNOWN = "unknown"
DRIFT_TYPES = frozenset({NO_DRIFT, CONFIGURATION_DRIFT, COMPATIBILITY_DRIFT, UNKNOWN})


@dataclass(frozen=True)
class RiskProfileDriftResult:
    """detect()/detect_version()'s complete, deterministic, read-only
    verdict for one (profile_id, scope_id) pair against one expected
    version.

    expected_version is the version this result was compared against --
    an explicit one for detect_version(), or whatever detect() resolved
    as the profile's own latest recorded version; None only when no
    valid expected state could be established at all (drift_type is
    then always UNKNOWN). actual_version is always
    LLMAgentRiskProfileService.get(profile_id).version -- the profile's
    real, live version number, read verbatim, never inferred.

    affected_actions/affected_capabilities/affected_policies are
    Commit #9's own LLMAgentRiskProfileImpactAnalyzer output for
    comparing the live profile against expected_version, reused
    verbatim -- this class computes no relationship of its own (Rule:
    "reuse existing compatibility and simulation logic instead of
    implementing another risk evaluator"). details lists every concrete
    fact this verdict was built from (which actions' resolved levels
    disagree, which compatibility reasons fired, a version-number
    mismatch), never just the conclusion.

    provenance embeds the full Commit #9 RiskProfileImpactResult this
    verdict was derived from, verbatim, the same "embed full source
    objects, never re-summarize" convention every result type in this
    whole risk lineage already keeps -- empty only for the UNKNOWN,
    no-valid-baseline case, where there was nothing to analyze.

    Zero side effects: detect()/detect_version() never mutate, persist,
    activate, deactivate, or roll back anything, and the same
    (profile_id, version, scope_id) against unchanged underlying state
    always produces an == result (Rules: "Detection is read-only and
    deterministic" / "No automatic repair").
    """

    profile_id: str
    scope_id: str
    expected_version: Optional[int]
    actual_version: int
    drift_detected: bool
    drift_type: str
    affected_actions: list
    affected_capabilities: list
    affected_policies: list
    details: list
    provenance: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["detected_at"] = self.detected_at.isoformat()
        return data
