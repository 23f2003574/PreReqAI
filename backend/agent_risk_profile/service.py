from backend.agent_policy_risk_assessment import LEVEL_LOW, LEVELS, InvalidActionContextError

from .in_memory_store import InMemoryRiskProfileStore
from .models import (
    ACTIVE,
    ARCHIVED,
    STATUSES,
    LLMAgentRiskProfile,
    RiskProfileActionRule,
    RiskProfileResolution,
    resolve_level,
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
    ACTIVE risk profile bound to the same specificity key at once (the
    same scope_id, and the same action_name/action_category/default
    binding -- see LLMAgentRiskProfileService._specificity_key()).

    A scope has at most one ACTIVE risk profile per specificity key at
    any time -- the same "one live record per identity" discipline this
    repository's own RiskThresholds (one current config per scope)
    already keeps, generalized (Commit #2) from "per scope" to "per
    (scope, specificity key)" so a scope-default profile and any number
    of distinctly-keyed exact-action/action-category profiles can
    coexist ACTIVE without ambiguity, while two profiles bound to the
    exact same key still cannot: archive the old one before creating its
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
        action_name: str = None,
        action_category: str = None,
    ) -> LLMAgentRiskProfile:
        """Record a new, version-1 risk profile for scope_id.

        action_name/action_category (Commit #2) optionally bind this
        profile to a specific action (exact tool_name match) or a
        broader action category, for
        backend.agent_risk_profile_resolution.LLMAgentRiskProfileResolver
        to select by specificity -- at most one of the two may be given;
        leaving both None (the default) creates an ordinary scope-default
        profile, exactly as Commit #1 originally defined create().

        Raises:
            InvalidRiskProfileError: If scope_id, name, default_level,
                action_name, or action_category is missing or invalid,
                or both action_name and action_category are given
            InvalidRiskProfileActionRuleError: If any action_rules entry
                is invalid
            DuplicateActionRuleIdError: If two action_rules share a
                rule_id
            InvalidRiskProfileStatusError: If status is given and is not
                one of STATUSES
            ActiveRiskProfileExistsError: If status is ACTIVE and
                scope_id already has an ACTIVE risk profile bound to the
                same specificity key (scope-default, or the same
                action_name/action_category)
        """
        self._validate_scope_id(scope_id)
        self._validate_name(name)
        self._validate_status(status)
        resolved_level = self._validate_default_level(default_level)
        resolved_rules = self._validate_action_rules(action_rules)
        action_name, action_category = self._validate_action_binding(action_name, action_category)

        if status == ACTIVE:
            new_key = self._specificity_key(action_name, action_category)
            for existing in self.store.list_for_scope(scope_id, status=ACTIVE):
                if self._specificity_key(existing.action_name, existing.action_category) == new_key:
                    raise ActiveRiskProfileExistsError(
                        f"scope {scope_id!r} already has an active risk profile for {new_key!r}; "
                        f"archive it first"
                    )

        profile = LLMAgentRiskProfile(
            scope_id=scope_id,
            name=name,
            action_rules=resolved_rules,
            default_level=resolved_level,
            status=status,
            version=1,
            action_name=action_name,
            action_category=action_category,
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
        """Resolve action_context against scope_id's current ACTIVE
        scope-default risk profile (action_name and action_category both
        None), if any.

        Returns None when scope_id has no ACTIVE scope-default risk
        profile at all -- existing default risk behavior remains
        entirely unchanged in that case, since there is nothing here to
        override it with. A scope may also have ACTIVE action-name- or
        action-category-bound profiles (Commit #2) that this method
        never considers -- selecting the most specific applicable
        profile across all three is
        backend.agent_risk_profile_resolution.LLMAgentRiskProfileResolver's
        own job; this method's scope-default-only behavior is exactly
        Commit #1's original resolve(), unchanged.

        When a scope-default ACTIVE profile exists, action_rules are
        checked in order; the first whose match constraints are
        satisfied by action_context wins. When none match, the
        profile's own default_level is used instead -- a selected
        profile always resolves to a definite level, it never falls
        through to None.

        Raises:
            InvalidRiskProfileError: If scope_id is missing
            InvalidActionContextError: If action_context is not a dict
        """
        self._validate_scope_id(scope_id)
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        defaults = [
            profile
            for profile in self.store.list_for_scope(scope_id, status=ACTIVE)
            if profile.action_name is None and profile.action_category is None
        ]
        if not defaults:
            return None
        profile = defaults[0]

        level, matched_rule_id, reason = resolve_level(profile, action_context)
        return RiskProfileResolution(
            profile_id=profile.profile_id,
            scope_id=scope_id,
            version=profile.version,
            level=level,
            matched_rule_id=matched_rule_id,
            reason=reason,
            provenance={"profile": profile, "action_context": dict(action_context)},
        )

    @staticmethod
    def _specificity_key(action_name, action_category):
        """The identity a risk profile's ACTIVE-uniqueness is keyed on:
        an exact action binding, an action-category binding, or (both
        None) the scope-default binding -- mirrors
        backend.session.execution_network_traffic_policy_service's own
        endpoint-specific-vs-runtime-wide key shape."""
        if action_name is not None:
            return ("action", action_name)
        if action_category is not None:
            return ("category", action_category)
        return ("default", None)

    @staticmethod
    def _validate_action_binding(action_name, action_category):
        if action_name is not None and (not isinstance(action_name, str) or not action_name.strip()):
            raise InvalidRiskProfileError("action_name must be a non-empty string when given")
        if action_category is not None and (
            not isinstance(action_category, str) or not action_category.strip()
        ):
            raise InvalidRiskProfileError("action_category must be a non-empty string when given")
        if action_name is not None and action_category is not None:
            raise InvalidRiskProfileError(
                "a risk profile may bind to action_name or action_category, not both"
            )
        return action_name, action_category

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
