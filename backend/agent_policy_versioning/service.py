from typing import Optional

from backend.agent_policy_engine import LLMAgentPolicyService
from backend.agent_policy_history import UPDATED, LLMAgentPolicyHistoryService

from .models import LLMAgentPolicyVersion


class UnknownPolicyVersionError(KeyError):
    """Raised when get_version()/diff() is given a version number that
    does not exist for policy_id."""


class LLMAgentPolicyVersionService:
    """Numbers, retrieves, and compares a Commit #1 policy's rule-set
    versions, computed entirely from Commit #10's own append-only change
    trail -- no parallel versioning system, no second store.

    list_versions()/get_version()/diff() are pure reads: every one of
    them re-derives its answer, on every call, from
    LLMAgentPolicyHistoryService.list(policy_id) -- the exact same
    already-immutable, already-ordered, already-redacted change records
    Commit #10 produces. A "version" is simply the subsequence of those
    changes whose own `rules` differ from the change immediately before
    it (a CREATED change always starts version 1; an ARCHIVED change, or
    an UPDATED that only touched name, never introduces a new version,
    since its rules are identical to the one before it; an
    EXCEPTION_CREATED/EXCEPTION_REVOKED change under the same policy_id
    carries no "rules" key at all and is skipped outright). Nothing here
    mutates, reorders, or rewrites a single Commit #10 record -- "do not
    silently rewrite historical versions" holds because there is nothing
    to rewrite: recomputing the same input always yields the same
    versions.

    create_version() is the one write path, and even it never invents a
    second mutation route: it calls Commit #1's own
    LLMAgentPolicyService.update(policy_id, rules=...) verbatim (so
    "current policy remains compatible with existing callers" -- nothing
    about Commit #1's own update() changes), then records that change via
    Commit #10's own LLMAgentPolicyHistoryService.record_change() when,
    and only when, the resulting rules actually differ from before --
    "each meaningful rule change creates a new version", and nothing
    else does. Calling create_version() with the policy's current,
    unchanged rules still goes through update() (matching Commit #1's own
    behavior verbatim) but records no new version, and simply returns
    the version that was already current.

    policy_service must be a bare Commit #1 LLMAgentPolicyService, never
    a Commit #10 LLMAgentPolicyHistoryTrackedService: create_version()
    already records the resulting change itself (with the given
    created_by as its actor), so wrapping a tracked service here would
    double-record every rule change, once with the actor create_version()
    was given and once more with whatever actor the tracked wrapper was
    constructed with. A caller who also wants every *other* kind of
    policy change (renames, archiving) tracked should still create and
    update non-rule fields through their own
    LLMAgentPolicyHistoryTrackedService instance, sharing the same
    underlying store and LLMAgentPolicyHistoryService this class is
    given -- the two compose safely as long as they are never the same
    object.
    """

    def __init__(self, policy_service: LLMAgentPolicyService, history_service: LLMAgentPolicyHistoryService):
        self._policy_service = policy_service
        self._history_service = history_service

    def create_version(
        self, policy_id: str, rules: list, created_by: str = None, reason: str = None
    ) -> Optional[LLMAgentPolicyVersion]:
        """Update policy_id's rules and, if they actually changed,
        record a new Commit #10 change for it -- then return the
        resulting current version (or the prior one unchanged, if
        nothing meaningful happened).

        reason, when given, is recorded on the Commit #10 change itself
        (e.g. Commit #12's rollback records why it rolled back) --
        forwarded verbatim to LLMAgentPolicyHistoryService.record_change(),
        never interpreted here.

        Raises:
            UnknownAgentPolicyError, ArchivedPolicyError,
            InvalidAgentPolicyError, InvalidPolicyRuleError,
            DuplicateRuleIdError: Propagated unchanged from Commit #1's
                own LLMAgentPolicyService.update()
        """
        before = self._policy_service.get(policy_id).to_dict()
        policy = self._policy_service.update(policy_id, rules=rules)
        after = policy.to_dict()

        if before["rules"] != after["rules"]:
            self._history_service.record_change(
                policy.scope_id, policy_id, UPDATED, before=before, after=after, actor=created_by, reason=reason,
            )

        return self._latest_version(policy_id)

    def list_versions(self, policy_id: str) -> list:
        """Every version of policy_id's rule set, oldest (version 1)
        first -- the complete history, never collapsed to just the
        latest."""
        versions = []
        previous_rules = None
        for change in self._history_service.list(policy_id):
            after = change.after or {}
            if "rules" not in after:
                continue  # not a policy rule-set snapshot (e.g. an exception change)

            rules = after["rules"]
            if versions and rules == previous_rules:
                continue  # this change did not touch rules at all

            versions.append(
                LLMAgentPolicyVersion(
                    policy_id=policy_id,
                    version=len(versions) + 1,
                    rules=rules,
                    created_at=change.created_at,
                    created_by=change.actor,
                    version_id=change.change_id,
                )
            )
            previous_rules = rules
        return versions

    def get_version(self, policy_id: str, version: int) -> LLMAgentPolicyVersion:
        """The one version of policy_id numbered `version`.

        Raises:
            UnknownPolicyVersionError: If policy_id has no such version
        """
        for entry in self.list_versions(policy_id):
            if entry.version == version:
                return entry
        raise UnknownPolicyVersionError(f"policy {policy_id!r} has no version {version}")

    def diff(self, policy_id: str, version_a: int, version_b: int) -> dict:
        """A deterministic, rule_id-keyed structural diff between two
        versions of policy_id's rule set.

        Raises:
            UnknownPolicyVersionError: If either version does not exist
        """
        rules_a = {rule["rule_id"]: rule for rule in self.get_version(policy_id, version_a).rules}
        rules_b = {rule["rule_id"]: rule for rule in self.get_version(policy_id, version_b).rules}

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

        return {
            "policy_id": policy_id,
            "version_a": version_a,
            "version_b": version_b,
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    def _latest_version(self, policy_id: str) -> Optional[LLMAgentPolicyVersion]:
        versions = self.list_versions(policy_id)
        return versions[-1] if versions else None
