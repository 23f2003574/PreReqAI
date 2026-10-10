from typing import Optional

from backend.agent_risk_profile import LLMAgentRiskProfile, LLMAgentRiskProfileService
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator

from .in_memory_store import InMemoryRiskProfileVersionStore
from .models import LLMAgentRiskProfileVersion
from .store import RiskProfileVersionStore


class UnknownRiskProfileVersionError(KeyError):
    """Raised when get_version()/diff() is given a version number that
    does not exist for profile_id."""


class InvalidRiskProfileVersionError(ValueError):
    """Raised when create_version()/diff() is given invalid arguments,
    or the profile would be invalid immediately after the requested
    update (Rule: "Validate before version creation")."""


def _definition_of(profile: LLMAgentRiskProfile) -> dict:
    """The part of profile that actually defines "how actions should be
    assessed" -- name, action_rules, default_level, and its Commit #2
    action_name/action_category specificity binding. Deliberately
    excludes status/created_at/updated_at/profile_id/version, which are
    record bookkeeping, not definition."""
    return {
        "name": profile.name,
        "action_rules": [rule.to_dict() for rule in profile.action_rules],
        "default_level": profile.default_level,
        "action_name": profile.action_name,
        "action_category": profile.action_category,
    }


class LLMAgentRiskProfileVersionService:
    """Records, retrieves, and compares immutable, numbered snapshots of
    a Commit #1 risk profile's own content over time.

    Not a parallel versioning system: version is exactly Commit #1's own
    LLMAgentRiskProfile.version int, reused verbatim rather than a
    second, independently-maintained sequence number -- Commit #1
    already bumps it precisely when action_rules or default_level
    actually change (never for a name-only edit), so this service never
    re-derives what counts as "a meaningful change", it only observes
    Commit #1's own already-proven signal. Mutation is never duplicated
    either: create_version() calls Commit #1's own
    LLMAgentRiskProfileService.update() verbatim for whichever fields a
    caller gives it (so "current profile behavior remains compatible
    with existing callers" holds -- nothing about update() itself
    changes), then records the resulting state as a new
    LLMAgentRiskProfileVersion only when profile.version actually
    advanced. This mirrors backend.agent_policy_versioning.
    LLMAgentPolicyVersionService's own "call the base service's real
    update(), record a version only when the content actually changed"
    discipline -- adapted to this series' own already-numbered profile
    record instead of re-deriving a sequence position from an external
    change trail every time, since Commit #1 of this series already
    carries that number directly.

    validate() is composed, not re-implemented: before ever persisting
    a new LLMAgentRiskProfileVersion, this service runs Commit #3's own
    LLMAgentRiskProfileValidator against the profile's post-update state
    and refuses to record a version for an invalid one (Rule: "Validate
    before version creation") -- defense in depth, since Commit #1's own
    update() already enforces the same constraints and should never
    produce an invalid profile in the first place.

    Versions are immutable and append-only: list_versions()/get_version()
    only ever read what create_version() already persisted, and nothing
    in this class ever calls save() twice for the same version_id or
    mutates a version's own definition/provenance after the fact (Rule:
    "Never silently rewrite historical definitions").
    """

    def __init__(
        self,
        profile_service: LLMAgentRiskProfileService,
        validator: LLMAgentRiskProfileValidator = None,
        store: RiskProfileVersionStore = None,
    ):
        self._profile_service = profile_service
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()
        self.store = store if store is not None else InMemoryRiskProfileVersionStore()

    def create_version(
        self,
        profile_id: str,
        name: str = None,
        action_rules: list = None,
        default_level: str = None,
        actor: str = None,
        reason: str = None,
    ) -> LLMAgentRiskProfileVersion:
        """Apply name/action_rules/default_level to profile_id (via
        Commit #1's own update(), whichever fields are given -- all
        three may be omitted to simply snapshot the profile's current,
        already-persisted state) and record the result as a new version
        if, and only if, profile.version actually advanced.

        Calling this with no field changed (or with fields identical to
        the current profile) still returns a version -- either the one
        already on record for the current profile.version, or, for a
        profile that has never had a version recorded at all (e.g. right
        after LLMAgentRiskProfileService.create()), a fresh one snapshotting
        its current state.

        Raises:
            UnknownRiskProfileError, ArchivedRiskProfileError,
            InvalidRiskProfileError, InvalidRiskProfileActionRuleError,
            DuplicateActionRuleIdError: Propagated unchanged from Commit
                #1's own LLMAgentRiskProfileService.update(), when any
                of name/action_rules/default_level is given
            InvalidRiskProfileVersionError: If the profile is invalid
                immediately after the update, per Commit #3's own
                LLMAgentRiskProfileValidator
        """
        before = self._profile_service.get(profile_id)

        if name is not None or action_rules is not None or default_level is not None:
            self._profile_service.update(
                profile_id, name=name, action_rules=action_rules, default_level=default_level
            )

        after = self._profile_service.get(profile_id)

        result = self._validator.validate(after)
        if not result.is_valid:
            raise InvalidRiskProfileVersionError(
                f"profile {profile_id!r} is invalid and cannot be versioned: "
                f"{[issue.to_dict() for issue in result.issues]}"
            )

        existing = self._version_for_number(profile_id, after.version)
        if existing is not None:
            return existing

        version = LLMAgentRiskProfileVersion(
            profile_id=profile_id,
            version=after.version,
            definition=_definition_of(after),
            provenance={
                "before": before.to_dict() if before.version != after.version else None,
                "after": after.to_dict(),
                "actor": actor,
                "reason": reason,
            },
        )
        return self.store.save(version)

    def get_version(self, profile_id: str, version: int) -> LLMAgentRiskProfileVersion:
        """The one version of profile_id numbered `version`.

        Raises:
            UnknownRiskProfileVersionError: If profile_id has no such
                version on record
        """
        found = self._version_for_number(profile_id, version)
        if found is None:
            raise UnknownRiskProfileVersionError(f"profile {profile_id!r} has no version {version} on record")
        return found

    def list_versions(self, profile_id: str) -> list:
        """Every version recorded for profile_id, oldest (lowest
        version number) first -- the complete history, never collapsed
        to just the latest."""
        return self.store.list_for_profile(profile_id)

    def diff(self, profile_id: str, version_a: int, version_b: int) -> dict:
        """A deterministic, rule_id-keyed structural diff of
        action_rules between two versions of profile_id, plus every
        flat field (name/default_level/action_name/action_category)
        that differs between them.

        Raises:
            UnknownRiskProfileVersionError: If either version does not
                exist on record
        """
        definition_a = self.get_version(profile_id, version_a).definition
        definition_b = self.get_version(profile_id, version_b).definition

        rules_a = {rule["rule_id"]: rule for rule in definition_a["action_rules"]}
        rules_b = {rule["rule_id"]: rule for rule in definition_b["action_rules"]}

        added = sorted(
            (rules_b[rule_id] for rule_id in rules_b if rule_id not in rules_a),
            key=lambda rule: rule["rule_id"],
        )
        removed = sorted(
            (rules_a[rule_id] for rule_id in rules_a if rule_id not in rules_b),
            key=lambda rule: rule["rule_id"],
        )
        changed = sorted(
            (
                {"rule_id": rule_id, "before": rules_a[rule_id], "after": rules_b[rule_id]}
                for rule_id in rules_a
                if rule_id in rules_b and rules_a[rule_id] != rules_b[rule_id]
            ),
            key=lambda entry: entry["rule_id"],
        )

        changed_fields = {
            field_name: {"before": definition_a[field_name], "after": definition_b[field_name]}
            for field_name in ("name", "default_level", "action_name", "action_category")
            if definition_a[field_name] != definition_b[field_name]
        }

        return {
            "profile_id": profile_id,
            "version_a": version_a,
            "version_b": version_b,
            "added": added,
            "removed": removed,
            "changed": changed,
            "changed_fields": changed_fields,
        }

    def _version_for_number(self, profile_id: str, version: int) -> Optional[LLMAgentRiskProfileVersion]:
        for entry in self.store.list_for_profile(profile_id):
            if entry.version == version:
                return entry
        return None
