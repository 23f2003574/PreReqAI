from backend.agent_policy_risk_assessment import LEVEL_LOW, LEVELS, InvalidActionContextError

from .in_memory_store import InMemoryRiskProfileStore
from .models import (
    ACTIVE,
    ARCHIVED,
    STATUSES,
    LLMAgentRiskProfile,
    RiskProfileActionRule,
    RiskProfileResolution,
)
from .store import RiskProfileStore


class UnknownRiskProfileError(KeyError):
    """Raised when get()/update()/archive() is given a profile_id that was never created."""


class InvalidRiskProfileError(ValueError):
    """Raised when a profile's scope_id, name, action_rules, or default_level fail validation."""


class InvalidRiskProfileStatusError(ValueError):
    """Raised when a status argument is not one of STATUSES."""


class DuplicateActionRuleIdError(InvalidRiskProfileError):
    """Raised when two action_rules within the same profile share a
    rule_id -- a rule_id must uniquely identify the rule responsible for
    a resolution within its own profile, so provenance never becomes
    ambiguous."""


class ArchivedRiskProfileError(ValueError):
    """Raised when update() is given a profile_id that is already ARCHIVED.

    An archived profile is retired, deliberately-preserved history --
    the same reasoning backend.agent_policy_engine.LLMAgentPolicyService
    already applies to an ARCHIVED policy. Reviving one requires a fresh
    create() call, not a mutation of the archived record, and an
    archived profile can never be selected by resolve() again.
    """


class ActiveRiskProfileExistsError(ValueError):
    """Raised when create() would leave a scope with more than one
    ACTIVE risk profile at once.

    A scope has at most one ACTIVE risk profile at any time -- the same
    "one live record per identity" discipline this repository's own
    RiskThresholds (one current config per scope) already keeps,
    applied here so resolve() never needs a precedence/conflict
    mechanism of its own to pick among several simultaneously-active
    profiles for the same scope: archive the old one before creating its
    replacement.
    """


class LLMAgentRiskProfileService:
    """Creates, reads, and retires named, versioned, scope-level risk
    profiles, and resolves an action_context against a scope's current
    ACTIVE profile.

    Not a second risk engine: this only configures which of
    backend.agent_policy_risk_assessment's own existing LEVEL_LOW/MEDIUM/
    HIGH/CRITICAL levels applies to a class of actions -- it never
    computes a score, never re-derives a level from risk factors, and
    never touches backend.agent_policy_risk_thresholds' own
    review_at/deny_at -> ALLOW/REVIEW/DENY mapping (that stays entirely
    that module's job, downstream of whatever level a caller resolves
    here). Persistence follows the exact save/get/list_for_scope split
    backend.agent_policy_engine.LLMAgentPolicyStore already established
    (an InMemoryRiskProfileStore by default, or a JSON-file-backed store
    built on the same backend.storage.AtomicJsonFile), and action_rules
    reuse backend.agent_policy_engine.LLMAgentPolicyRule.match's own
    {field: expected} matching shape (mirrored locally, the same
    same-shape-reimplementation precedent this series already set for
    reusing a shape across unrelated domains without a cross-module
    import) rather than a second matching scheme.

    resolve() never mutates a profile, never persists anything, and
    returns None -- rather than an invented "no override" level -- when
    scope_id has no ACTIVE risk profile at all, so a caller's existing
    default risk behavior (the assessor's own scoring, and the
    threshold service's own default review_at/deny_at) is left entirely
    unchanged in that case.
    """

    def __init__(self, store: RiskProfileStore = None):
        self.store = store if store is not None else InMemoryRiskProfileStore()

    def create(
        self,
        scope_id: str,
        name: str,
        action_rules: list = None,
        default_level: str = None,
        status: str = ACTIVE,
    ) -> LLMAgentRiskProfile:
        """Record a new, version-1 risk profile for scope_id.

        Raises:
            InvalidRiskProfileError: If scope_id, name, or default_level
                is missing or invalid
            InvalidRiskProfileActionRuleError: If any action_rules entry
                is invalid
            DuplicateActionRuleIdError: If two action_rules share a
                rule_id
            InvalidRiskProfileStatusError: If status is given and is not
                one of STATUSES
            ActiveRiskProfileExistsError: If status is ACTIVE and
                scope_id already has an ACTIVE risk profile
        """
        self._validate_scope_id(scope_id)
        self._validate_name(name)
        self._validate_status(status)
        resolved_level = self._validate_default_level(default_level)
        resolved_rules = self._validate_action_rules(action_rules)

        if status == ACTIVE and self.store.list_for_scope(scope_id, status=ACTIVE):
            raise ActiveRiskProfileExistsError(
                f"scope {scope_id!r} already has an active risk profile; archive it first"
            )

        profile = LLMAgentRiskProfile(
            scope_id=scope_id,
            name=name,
            action_rules=resolved_rules,
            default_level=resolved_level,
            status=status,
            version=1,
        )
        return self.store.save(profile)

    def get(self, profile_id: str) -> LLMAgentRiskProfile:
        profile = self.store.get(profile_id)
        if profile is None:
            raise UnknownRiskProfileError(profile_id)
        return profile

    def list(self, scope_id: str, status: str = None) -> list:
        self._validate_scope_id(scope_id)
        if status is not None:
            self._validate_status(status)
        return self.store.list_for_scope(scope_id, status)

    def update(
        self,
        profile_id: str,
        name: str = None,
        action_rules: list = None,
        default_level: str = None,
    ) -> LLMAgentRiskProfile:
        """Update one or more of name/action_rules/default_level on an
        existing, still-ACTIVE profile. Fields left as None are
        unchanged. Changing action_rules or default_level to something
        that actually differs from the current value bumps version;
        renaming a profile never does.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
            ArchivedRiskProfileError: If profile_id is already ARCHIVED
            InvalidRiskProfileError, InvalidRiskProfileActionRuleError,
                DuplicateActionRuleIdError: If a given field fails
                validation
        """
        profile = self.get(profile_id)
        if profile.status == ARCHIVED:
            raise ArchivedRiskProfileError(f"risk profile {profile_id!r} is archived and cannot be updated")

        changed = False
        if name is not None:
            self._validate_name(name)
            profile.name = name
        if action_rules is not None:
            resolved_rules = self._validate_action_rules(action_rules)
            if resolved_rules != profile.action_rules:
                changed = True
            profile.action_rules = resolved_rules
        if default_level is not None:
            resolved_level = self._validate_default_level(default_level)
            if resolved_level != profile.default_level:
                changed = True
            profile.default_level = resolved_level

        if changed:
            profile.version += 1

        return self.store.save(profile)

    def archive(self, profile_id: str) -> LLMAgentRiskProfile:
        """Retire profile_id by marking it ARCHIVED, never by deleting
        it -- an archived profile stays exactly as reachable through
        get()/list() as any other. Idempotent: archiving an
        already-ARCHIVED profile simply returns it unchanged. An
        ARCHIVED profile can never be selected by resolve() again.

        Raises:
            UnknownRiskProfileError: If profile_id was never created
        """
        profile = self.get(profile_id)
        if profile.status == ARCHIVED:
            return profile

        profile.status = ARCHIVED
        return self.store.save(profile)

    def resolve(self, scope_id: str, action_context: dict):
        """Resolve action_context against scope_id's current ACTIVE risk
        profile, if any.

        Returns None when scope_id has no ACTIVE risk profile at all --
        existing default risk behavior remains entirely unchanged in
        that case, since there is nothing here to override it with.

        When an ACTIVE profile exists, action_rules are checked in
        order; the first whose match constraints are satisfied by
        action_context wins. When none match, the profile's own
        default_level is used instead -- a selected profile always
        resolves to a definite level, it never falls through to None.

        Raises:
            InvalidRiskProfileError: If scope_id is missing
            InvalidActionContextError: If action_context is not a dict
        """
        self._validate_scope_id(scope_id)
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        active = self.store.list_for_scope(scope_id, status=ACTIVE)
        if not active:
            return None
        profile = active[0]

        for rule in profile.action_rules:
            if self._matches(rule.match, action_context):
                return RiskProfileResolution(
                    profile_id=profile.profile_id,
                    scope_id=scope_id,
                    version=profile.version,
                    level=rule.level,
                    matched_rule_id=rule.rule_id,
                    reason=rule.reason or f"action_rule {rule.rule_id!r} matched",
                    provenance={"profile": profile, "action_context": dict(action_context)},
                )

        return RiskProfileResolution(
            profile_id=profile.profile_id,
            scope_id=scope_id,
            version=profile.version,
            level=profile.default_level,
            matched_rule_id=None,
            reason=f"no action_rule matched; using profile {profile.profile_id!r}'s default_level",
            provenance={"profile": profile, "action_context": dict(action_context)},
        )

    @staticmethod
    def _matches(match: dict, action_context: dict) -> bool:
        for field_name, expected in match.items():
            if field_name not in action_context:
                return False
            actual = action_context[field_name]
            if isinstance(expected, (list, tuple, set, frozenset)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskProfileError("scope_id is required and must identify a project/notebook/API")

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str):
            raise InvalidRiskProfileError("name is required")

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidRiskProfileStatusError(f"status {status!r} is not one of {sorted(STATUSES)}")

    @staticmethod
    def _validate_default_level(default_level):
        if default_level is None:
            return LEVEL_LOW
        if default_level not in LEVELS:
            raise InvalidRiskProfileError(f"default_level {default_level!r} is not one of {LEVELS}")
        return default_level

    @staticmethod
    def _validate_action_rules(action_rules) -> list:
        if action_rules is None:
            return []
        if not isinstance(action_rules, list):
            raise InvalidRiskProfileError("action_rules must be a list")

        resolved = []
        seen_ids = set()
        for rule in action_rules:
            if isinstance(rule, RiskProfileActionRule):
                resolved_rule = rule
            elif isinstance(rule, dict):
                resolved_rule = RiskProfileActionRule.from_dict(rule)
            else:
                raise InvalidRiskProfileError(
                    f"each action_rule must be a RiskProfileActionRule or dict, got {type(rule).__name__}"
                )

            if resolved_rule.rule_id in seen_ids:
                raise DuplicateActionRuleIdError(
                    f"rule_id {resolved_rule.rule_id!r} is duplicated within this risk profile"
                )
            seen_ids.add(resolved_rule.rule_id)
            resolved.append(resolved_rule)
        return resolved
