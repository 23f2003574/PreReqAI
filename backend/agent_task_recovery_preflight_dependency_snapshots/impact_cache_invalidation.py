from datetime import datetime, timezone

from backend.agent_task_events import DEPENDENCY_ADDED, DEPENDENCY_REMOVED, LIFECYCLE_TRANSITIONED

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationOutcome,
    AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult,
)

IMPACT_CACHE_INVALIDATED_EVENT_TYPE = "dependency_impact_cache_invalidated"

TRIGGER_DEPENDENCY = "dependency"
TRIGGER_PREFLIGHT = "preflight"
TRIGGER_SNAPSHOT = "snapshot"
TRIGGER_RECONCILE = "reconcile"

_EDGE_EVENT_TYPES = (DEPENDENCY_ADDED, DEPENDENCY_REMOVED)
_DEPENDENCY_EVENT_TYPES = (DEPENDENCY_ADDED, DEPENDENCY_REMOVED, LIFECYCLE_TRANSITIONED)


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError(ValueError):
    """Raised when any operation here is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService:
    """Removes cached dependency-impact entries the moment a change makes
    them stale -- never a second cache or event system (Rule: "Do not
    create another cache/event system"): every removal is #1's own
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheService.invalidate(),
    every change signal is an existing source (the task event stream,
    the preflight store/invalidation service, the snapshot service), and
    this class holds no entry state of its own.

    Invalidates only entries whose evidence can be affected (Rule): an
    entry's dependency evidence is every dependency id in its bound
    snapshot plus every id its result reported as added/removed/resolved/
    blocked/changed. invalidate_for_dependency() removes an entry only if
    dependency_id is in that evidence, or -- when a dependency_service is
    given -- is currently reachable from task_id (an edge added since the
    entry was computed has no evidence yet, by definition). An entry whose
    evidence cannot be established (its snapshot no longer loads) is
    treated as affected: fail closed, never keep what cannot be checked.
    Entries for other preflights, or for dependencies outside the
    evidence, are left intact and reported in retained_preflight_ids.

    reconcile(task_id) is the change-detection pass. Per entry it applies,
    in one place, every existing signal: the entry is no longer its
    preflight's current snapshot/version (#1's is_current()); its
    preflight was invalidated or superseded (the guardrails' own
    preflight invalidation service / preflight store, when given); or --
    with an event_query_service -- a DEPENDENCY_ADDED/REMOVED event on
    task_id, or a DEPENDENCY_ADDED/REMOVED/LIFECYCLE_TRANSITIONED event
    on any evidence dependency, was recorded at or after the moment the
    entry's result was computed (its own reconciled_at). Events are
    compared by time against the entry, so a repeated pass never removes
    an entry recomputed after the change. A lifecycle transition of
    task_id itself is deliberately NOT a signal: it does not alter its
    dependencies' state.

    Idempotent (Rule): removal is cache.invalidate(), itself idempotent,
    and a second pass finds nothing left to remove. The explicit
    invalidate_for_*() calls assert "this changed now", so calling one
    again after the entry was recomputed removes the fresh entry too --
    the cost is one extra fresh analysis, never a stale result.

    History (Rule: preserve if supported): #1's cache keeps no history, so
    each result carries full per-entry metadata, and -- with an
    event_service -- every entry actually removed is appended to the
    existing task event stream under
    IMPACT_CACHE_INVALIDATED_EVENT_TYPE (references only; the same
    pattern trust_history.py already uses). Emitting never influences
    the invalidation.

    Never executes or mutates recovery state (Rule): the only writes are
    cache removals and that optional event append; nothing here holds a
    lifecycle, scheduling or authorization collaborator.
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        snapshot_service=None,
        dependency_service=None,
        preflight_store=None,
        preflight_invalidation_service=None,
        event_query_service=None,
        event_service=None,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the real one
                holding the entries to be invalidated.
            snapshot_service: Optional, duck-typed (get() only); enables
                snapshot-derived dependency evidence.
            dependency_service: Optional, duck-typed (get_dependencies()
                only); lets invalidate_for_dependency() also match a
                dependency currently reachable from task_id.
            preflight_store: Optional, duck-typed (get(task_id) only);
                enables the "preflight superseded" signal. No default: a
                fresh empty store would report every preflight superseded.
            preflight_invalidation_service: Optional, duck-typed
                (get_invalidation() only); enables "preflight invalidated".
            event_query_service: Optional LLMAgentTaskEventQueryService
                (query() only); enables the event-driven signals.
            event_service: Optional LLMAgentTaskEventService (emit()
                only); enables the history append.
        """
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._snapshot_service = snapshot_service
        self._dependency_service = dependency_service
        self._preflight_store = preflight_store
        self._preflight_invalidation_service = preflight_invalidation_service
        self._event_query_service = event_query_service
        self._event_service = event_service

    def invalidate_for_dependency(
        self, task_id: str, dependency_id: str
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
        """Remove task_id's entries whose evidence dependency_id can affect.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError:
                If task_id or dependency_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(dependency_id, "dependency_id")

        reachable = (
            set(self._dependency_service.get_dependencies(task_id, transitive=True))
            if self._dependency_service is not None
            else set()
        )
        selected = []
        for entry in self._cache_service.list_entries(task_id):
            evidence = self._evidence_ids(task_id, entry)
            if evidence is None:
                selected.append((entry, (f"dependency {dependency_id!r} changed and this entry's evidence cannot be verified",)))
            elif dependency_id in evidence or dependency_id in reachable:
                selected.append((entry, (f"dependency {dependency_id!r} changed",)))
        return self._apply(task_id, TRIGGER_DEPENDENCY, dependency_id, selected)

    def invalidate_for_preflight(
        self, task_id: str, preflight_id: str
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
        """Remove task_id's entry bound to preflight_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError:
                If task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        selected = [
            (entry, (f"preflight {preflight_id!r} changed",))
            for entry in self._cache_service.list_entries(task_id)
            if entry.preflight_id == preflight_id
        ]
        return self._apply(task_id, TRIGGER_PREFLIGHT, preflight_id, selected)

    def invalidate_for_snapshot(
        self, task_id: str, snapshot_id: str
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
        """Remove task_id's entries bound to snapshot_id, plus -- when
        snapshot_id is a known snapshot -- any entry of that snapshot's
        preflight that snapshot has replaced.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        snapshot = self._snapshot_service.get(task_id, snapshot_id) if self._snapshot_service is not None else None
        selected = []
        for entry in self._cache_service.list_entries(task_id):
            if entry.snapshot_id == snapshot_id:
                selected.append((entry, (f"snapshot {snapshot_id!r} changed",)))
            elif (
                snapshot is not None
                and entry.preflight_id == snapshot.preflight_id
                and not self._cache_service.is_current(entry)
            ):
                selected.append((entry, (f"snapshot {entry.snapshot_id!r} was replaced by {snapshot_id!r}",)))
        return self._apply(task_id, TRIGGER_SNAPSHOT, snapshot_id, selected)

    def reconcile(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
        """Detect and remove every stale entry cached for task_id, from
        the existing change signals -- see the class docstring.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")

        selected = []
        for entry in self._cache_service.list_entries(task_id):
            reasons = list(self.stale_reasons(task_id, entry))
            if reasons:
                selected.append((entry, tuple(reasons)))
        return self._apply(task_id, TRIGGER_RECONCILE, None, selected)

    def stale_reasons(self, task_id: str, entry) -> tuple:
        """Every reason entry is stale right now -- () when none is
        found. A pure read (it queries, never removes), exposed so the
        eviction service reuses these exact signals instead of
        re-deriving them; reconcile() removes exactly what this reports."""
        reasons = []
        if not self._cache_service.is_current(entry):
            reasons.append("snapshot/version is no longer the preflight's current one")

        if self._preflight_invalidation_service is not None:
            invalidation = self._preflight_invalidation_service.get_invalidation(entry.preflight_id)
            if invalidation is not None:
                reasons.append(f"preflight was invalidated: {invalidation.reason}")
        if self._preflight_store is not None:
            current = self._preflight_store.get(task_id)
            if current is None or current.preflight_id != entry.preflight_id:
                reasons.append("preflight is no longer the task's current preflight")

        if self._event_query_service is not None:
            evidence = self._evidence_ids(task_id, entry)
            if evidence is None:
                reasons.append("dependency evidence cannot be verified")
            reasons.extend(self._event_reasons(task_id, entry, evidence or set()))
        return tuple(reasons)

    def _event_reasons(self, task_id: str, entry, evidence: set) -> list:
        since = entry.result.reconciled_at
        reasons = []
        watched = [(task_id, _EDGE_EVENT_TYPES)] + [(dependency, _DEPENDENCY_EVENT_TYPES) for dependency in sorted(evidence)]
        for watched_task_id, event_types in watched:
            events = self._event_query_service.query(task_id=watched_task_id, event_types=event_types, start_time=since)
            if events:
                latest = events[-1]
                reasons.append(f"{latest.event_type} event on {watched_task_id!r} at {latest.occurred_at.isoformat()}")
        return reasons

    def _evidence_ids(self, task_id: str, entry):
        """Every dependency id entry's result can depend on -- None when
        its bound snapshot is expected but cannot be loaded."""
        result = entry.result
        ids = set(result.added) | set(result.removed) | set(result.resolved) | set(result.blocked)
        ids |= {change.dependency_task_id for change in result.changed}
        if self._snapshot_service is not None:
            snapshot = self._snapshot_service.get(task_id, entry.snapshot_id)
            if snapshot is None:
                return None
            ids |= {dependency.dependency_task_id for dependency in snapshot.dependencies}
        return ids

    def _apply(self, task_id, trigger, subject_id, selected) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
        selected_ids = {entry.preflight_id for entry, _ in selected}
        retained = tuple(
            entry.preflight_id for entry in self._cache_service.list_entries(task_id) if entry.preflight_id not in selected_ids
        )

        outcomes = []
        for entry, reasons in selected:
            removal = self._cache_service.invalidate(task_id, entry.preflight_id, reason="; ".join(reasons))
            if removal.invalidated:
                self._record(task_id, entry, trigger, reasons)
            outcomes.append(
                AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationOutcome(
                    preflight_id=entry.preflight_id, snapshot_id=entry.snapshot_id, version=entry.version,
                    invalidated=removal.invalidated, reasons=reasons,
                )
            )

        return AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult(
            task_id=task_id, trigger=trigger, subject_id=subject_id, affected=tuple(outcomes),
            retained_preflight_ids=retained, invalidated_count=sum(1 for outcome in outcomes if outcome.invalidated),
            checked_at=datetime.now(timezone.utc),
        )

    def _record(self, task_id, entry, trigger, reasons) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.emit(
                task_id,
                IMPACT_CACHE_INVALIDATED_EVENT_TYPE,
                payload={
                    "preflight_id": entry.preflight_id, "snapshot_id": entry.snapshot_id, "version": entry.version,
                    "trigger": trigger, "reasons": list(reasons),
                },
            )
        except Exception:
            pass  # history is best-effort; it must never influence the invalidation

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
