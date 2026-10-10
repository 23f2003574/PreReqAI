from datetime import datetime, timezone
from typing import Optional

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .models import (
    CHANGED,
    UNCHANGED,
    AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult,
    AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyViolation,
    AgentTaskRecoveryPreflightDependencyImpactCacheRepairAction,
    AgentTaskRecoveryPreflightDependencyImpactCacheRepairResult,
    AgentTaskRecoveryPreflightDependencySnapshotReconciliation,
)
from .reconciliation import LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService

IMPACT_CACHE_REPAIRED_EVENT_TYPE = "dependency_impact_cache_repaired"

MISSING = "missing"        # no entry, though a trusted current snapshot could produce one
STALE = "stale"            # entry bound to a snapshot/version that is no longer current
MISMATCHED = "mismatched"  # entry's own identity disagrees with the result it holds
CORRUPTED = "corrupted"    # entry's result is malformed or contradicts itself
DIVERGED = "diverged"      # entry no longer matches the live dependency evidence (deep only)
UNTRUSTED = "untrusted"    # trust in the current snapshot cannot be established
CONSISTENCY_CATEGORIES = frozenset({MISSING, STALE, MISMATCHED, CORRUPTED, DIVERGED, UNTRUSTED})

RECOMPUTED = "recomputed"
REMOVED = "removed"
KEPT_NEWER = "kept_newer"
UNREPAIRABLE = "unrepairable"
REPAIR_ACTIONS = frozenset({RECOMPUTED, REMOVED, KEPT_NEWER, UNREPAIRABLE})

_CONTENT_FIELDS = ("added", "removed", "resolved", "blocked", "changed")


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError(ValueError):
    """Raised when check()/repair() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService:
    """Detects cache entries that no longer agree with the evidence they
    were computed from, and repairs them -- never another cache or
    dependency resolver (Rule): entries are read and replaced only
    through #1's cache, the live evidence is Commit #1's own read-only
    snapshot diff(), trust is the cache's own gate, and a repair's
    recompute is Commit #2's own reconcile(). check() mirrors this
    repository's consistency convention (backend.agent_task_events'
    LLMAgentTaskEventConsistencyService): read-only, deterministic, a
    tuple of categorised violations, is_consistent = not violations,
    nothing persisted.

    Per preflight (the one named, or every cached one plus the task's
    current preflight when a preflight_store is wired, so a missing entry
    for it is visible):
      CORRUPTED / MISMATCHED -- the entry alone: its result is not a
        reconciliation result, is malformed, is unreliable, has a status
        that contradicts its recorded changes (UNCHANGED with changes, or
        CHANGED with none), or carries a different task/preflight/
        snapshot/version than the entry itself.
      STALE -- the entry's snapshot/version is not the current identity.
      UNTRUSTED -- the CURRENT snapshot fails the cache's trust gate (or
        it errors). Fail closed: no evidence from it is compared, no
        MISSING/DIVERGED is asserted, and repair() will not recompute.
      MISSING -- trusted current snapshot, no entry.
      DIVERGED -- deep=True only, current identity, trusted, uncorrupted:
        the entry's added/removed/resolved/blocked/changed differ from a
        fresh snapshot diff(). This is the one check that costs a live
        dependency read, so the cache-consumption path calls check() with
        deep=False and gets every cheap check without it.

    repair() acts only on what check() found: UNTRUSTED preflights are
    left alone (UNREPAIRABLE); for the rest it re-verifies the entry is
    unchanged since the check, removes it, and recomputes through
    reconcile(use_cache=False) and cache.put(). Never overwrites newer
    evidence: an entry that changed since the check is left (KEPT_NEWER),
    as is one a concurrent writer replaced with a newer result during the
    recompute (put() itself refuses to overwrite it). A second repair
    finds nothing to fix. Repair never executes or reschedules recovery
    and holds no such collaborator. With an event_service, every action
    is appended as references under IMPACT_CACHE_REPAIRED_EVENT_TYPE
    (best-effort; a failure never blocks a repair) -- the same history
    pattern #2 and #5 use; check() records nothing.
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService = None,
        preflight_store=None,
        event_service=None,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the real one.
            snapshot_service: Defaults to a fresh one; pass the real one
                (diff() is called for the deep check).
            reconciliation_service: Defaults to a fresh one over
                snapshot_service; pass the real, wired one for repair()
                to recompute through.
            preflight_store: Optional, duck-typed (get(task_id) only);
                lets check() notice a missing entry for the task's
                current preflight.
            event_service: Optional LLMAgentTaskEventService (emit() only).
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
                snapshot_service=self._snapshot_service
            )
        )
        self._preflight_store = preflight_store
        self._event_service = event_service

    def check(
        self, task_id: str, preflight_id: Optional[str] = None, deep: bool = True, verify_trust: bool = True
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult:
        """Compare task_id's cached impact against its current trusted
        snapshot/version -- read-only.

        verify_trust=False skips the trust gate, for a caller that has
        JUST passed the cache's own lookup (which enforces the same gate)
        and must not pay for a second validation; every other caller
        should leave it on.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError:
                If task_id is not a non-empty string, or preflight_id is
                given and is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if preflight_id is not None:
            self._require_text(preflight_id, "preflight_id")

        entries = {entry.preflight_id: entry for entry in self._cache_service.list_entries(task_id)}
        if preflight_id is not None:
            preflight_ids = [preflight_id]
        else:
            ids = set(entries)
            current = self._preflight_store.get(task_id) if self._preflight_store is not None else None
            if current is not None:
                ids.add(current.preflight_id)
            preflight_ids = sorted(ids)

        violations = []
        for pid in preflight_ids:
            violations.extend(self._check_one(task_id, pid, entries.get(pid), deep, verify_trust))
        return AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult(
            task_id=task_id, preflight_id=preflight_id, is_consistent=not violations, violations=tuple(violations),
            checked_preflight_ids=tuple(preflight_ids), deep=deep, checked_at=datetime.now(timezone.utc),
        )

    def repair(
        self, task_id: str, preflight_id: Optional[str] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheRepairResult:
        """Repair every inconsistency check() finds -- see the class
        docstring. Idempotent.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError:
                If task_id is not a non-empty string, or preflight_id is
                given and is not a non-empty string
        """
        before = self.check(task_id, preflight_id)
        by_preflight: dict = {}
        for violation in before.violations:
            by_preflight.setdefault(violation.preflight_id, []).append(violation)

        actions = []
        for pid, found in by_preflight.items():
            action = self._repair_one(task_id, pid, found)
            actions.append(action)
            self._record(task_id, action)

        after = self.check(task_id, preflight_id)
        return AgentTaskRecoveryPreflightDependencyImpactCacheRepairResult(
            task_id=task_id, preflight_id=preflight_id, before=before, actions=tuple(actions), after=after,
            repaired_count=sum(1 for action in actions if action.action in (RECOMPUTED, REMOVED)),
            is_consistent=after.is_consistent, repaired_at=datetime.now(timezone.utc),
        )

    def _check_one(self, task_id: str, preflight_id: str, entry, deep: bool, verify_trust: bool = True) -> list:
        def violation(category, reason, snapshot_id=None, version=None):
            return AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyViolation(
                preflight_id=preflight_id, snapshot_id=snapshot_id, version=version, category=category, reason=reason
            )

        found = []
        entry_ids = (entry.snapshot_id, entry.version) if entry is not None else (None, None)
        structural = self._structural_violations(entry) if entry is not None else []
        found.extend(violation(category, reason, *entry_ids) for category, reason in structural)

        identity = self._cache_service.current_identity(task_id, preflight_id)
        if identity is None:
            if entry is not None:
                found.append(violation(STALE, "the preflight has no current snapshot", *entry_ids))
            return found

        if entry is not None and identity != entry_ids:
            found.append(violation(STALE, "entry is bound to a snapshot/version that is no longer current", *entry_ids))
        if verify_trust and not self._cache_service.is_trusted(task_id, identity[0]):
            found.append(violation(UNTRUSTED, "trust in the current snapshot cannot be established", *identity))
            return found  # fail closed: no evidence from an untrusted snapshot is compared
        if entry is None:
            found.append(violation(MISSING, "no cached impact for a trusted current snapshot", *identity))
        elif deep and not structural and identity == entry_ids:
            try:
                diff = self._snapshot_service.diff(task_id, entry.snapshot_id)
            except Exception as error:
                found.append(violation(DIVERGED, f"live dependency evidence could not be read: {error}", *entry_ids))
            else:
                live = (diff.added, diff.removed, diff.resolved, diff.newly_blocked, diff.state_changed)
                cached = tuple(getattr(entry.result, name) for name in _CONTENT_FIELDS)
                if tuple(tuple(x) for x in cached) != tuple(tuple(x) for x in live):
                    found.append(violation(DIVERGED, "entry no longer matches the live dependency evidence", *entry_ids))
        return found

    @staticmethod
    def _structural_violations(entry) -> list:
        result = entry.result
        if not isinstance(result, AgentTaskRecoveryPreflightDependencySnapshotReconciliation):
            return [(CORRUPTED, "cached result is not a reconciliation result")]
        problems = []
        if not all(isinstance(getattr(result, name, None), (tuple, list)) for name in _CONTENT_FIELDS):
            problems.append((CORRUPTED, "cached result's dependency fields are malformed"))
        elif result.status not in (UNCHANGED, CHANGED) or result.reliable is not True:
            problems.append((CORRUPTED, "cached result is not a reliable unchanged/changed verdict"))
        elif (result.status == CHANGED) != any(getattr(result, name) for name in _CONTENT_FIELDS):
            problems.append((CORRUPTED, f"status {result.status!r} contradicts the recorded changes"))
        if (result.task_id, result.preflight_id, result.snapshot_id, result.version) != (
            entry.task_id, entry.preflight_id, entry.snapshot_id, entry.version
        ):
            problems.append((MISMATCHED, "entry's identity disagrees with the result it holds"))
        return problems

    def _repair_one(self, task_id: str, preflight_id: str, found: list):
        categories = tuple(sorted({violation.category for violation in found}))

        def action(name, reason):
            return AgentTaskRecoveryPreflightDependencyImpactCacheRepairAction(
                preflight_id=preflight_id, categories=categories, action=name, reason=reason
            )

        if UNTRUSTED in categories:
            return action(UNREPAIRABLE, "trust in the current snapshot cannot be established; nothing was changed")
        identity = self._cache_service.current_identity(task_id, preflight_id)
        current = next((e for e in self._cache_service.list_entries(task_id) if e.preflight_id == preflight_id), None)
        seen = next((v for v in found if v.snapshot_id is not None and v.category != MISSING), None)
        if current is not None and (
            seen is None or (current.snapshot_id, current.version) != (seen.snapshot_id, seen.version)
        ):
            return action(KEPT_NEWER, "the entry changed since it was checked; it was left as is")
        if current is None and MISSING not in categories:
            return action(KEPT_NEWER, "the entry was removed since it was checked")

        if current is not None:
            self._cache_service.invalidate(task_id, preflight_id, reason="consistency repair: " + ", ".join(categories))
        if identity is None:
            return action(REMOVED, "no current snapshot to recompute from; the entry was removed")
        try:
            impact = self._reconciliation_service.reconcile(task_id, identity[0], use_cache=False)
            stored = self._cache_service.put(task_id, preflight_id, impact)
        except Exception as error:
            return action(REMOVED, f"the entry was removed but could not be recomputed: {error}")
        if stored is None:
            return action(REMOVED, "the entry was removed; the recomputed result was not cacheable")
        if stored.result.reconciled_at > impact.reconciled_at:
            return action(KEPT_NEWER, "a newer entry was written concurrently and was kept")
        return action(RECOMPUTED, "the entry was replaced from the current trusted snapshot")

    def _record(self, task_id: str, action) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.emit(
                task_id,
                IMPACT_CACHE_REPAIRED_EVENT_TYPE,
                payload={
                    "preflight_id": action.preflight_id, "categories": list(action.categories),
                    "action": action.action, "reason": action.reason,
                },
            )
        except Exception:
            pass  # history is best-effort; it must never block a repair

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError(
                f"{field_name} is required and must be a non-empty string"
            )
