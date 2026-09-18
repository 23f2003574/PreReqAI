from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from .impact_cache_metrics import MISS_NOT_CACHED, MISS_STALE, MISS_UNTRUSTED
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheEntry,
    AgentTaskRecoveryPreflightDependencyImpactCacheInvalidation,
    AgentTaskRecoveryPreflightDependencySnapshotReconciliation,
)
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError(ValueError):
    """Raised when get()/put()/invalidate() is given invalid arguments, or
    put() is given a result that does not belong to task_id/preflight_id."""


class AgentTaskRecoveryPreflightDependencyImpactCacheStore(ABC):
    """Raw storage for AgentTaskRecoveryPreflightDependencyImpactCacheEntry
    records, one per (task_id, preflight_id). In-memory only, unlike this
    package's other stores: a cached result is derived data that embeds
    opaque integrity/signature objects (no to_dict/from_dict exists for
    it), and losing it on restart only costs one fresh analysis."""

    @abstractmethod
    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightDependencyImpactCacheEntry]:
        ...

    @abstractmethod
    def save(
        self, entry: AgentTaskRecoveryPreflightDependencyImpactCacheEntry
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheEntry:
        ...

    @abstractmethod
    def delete(self, task_id: str, preflight_id: str) -> bool:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryPreflightDependencyImpactCacheStore(AgentTaskRecoveryPreflightDependencyImpactCacheStore):
    def __init__(self):
        self._entries: dict = {}

    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightDependencyImpactCacheEntry]:
        entry = self._entries.get((task_id, preflight_id))
        return deepcopy(entry) if entry is not None else None

    def save(
        self, entry: AgentTaskRecoveryPreflightDependencyImpactCacheEntry
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheEntry:
        self._entries[(entry.task_id, entry.preflight_id)] = deepcopy(entry)
        return deepcopy(entry)

    def delete(self, task_id: str, preflight_id: str) -> bool:
        return self._entries.pop((task_id, preflight_id), None) is not None

    def list_for_task(self, task_id: str) -> list:
        matching = [entry for (entry_task_id, _), entry in self._entries.items() if entry_task_id == task_id]
        return [deepcopy(entry) for entry in sorted(matching, key=lambda item: (item.cached_at, item.preflight_id))]


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheService:
    """Memoizes the dependency-impact result reconcile() produces for a
    preflight, so repeated recovery preflight checks against an unchanged
    snapshot skip the fresh diff -- never a second impact-analysis engine
    and never a generic cache layer: the cached value is Commit #2's own
    AgentTaskRecoveryPreflightDependencySnapshotReconciliation, carried
    through verbatim, and this class never computes one itself.

    Exact-identity keyed (Rule): an entry is bound to the (snapshot_id,
    version) it was computed for. get() resolves the CURRENT identity of
    task_id/preflight_id through the existing version service's
    latest_version() (or, with no version service, the snapshot service's
    latest_for_preflight()) and treats any mismatch as a miss -- so
    capturing a new snapshot/version implicitly invalidates the old entry
    with no notification needed. put() refuses a result that is not for
    the current identity, so a stale result can never be stored.

    Fail-closed on trust (Rule): when a trust_service (or, failing that,
    an integrity_service) is configured, get() re-validates the entry's
    snapshot on EVERY lookup and returns None unless it is still trusted/
    valid; a cache hit never bypasses trust. Only reliable results are
    ever cached -- an INDETERMINATE result (untrusted snapshot, failed
    resolution) is a transient failure, not a fact worth remembering.

    Sharp edge, by design: a change to the LIVE dependency graph (a
    dependency completing, an edge being added/removed) that does not
    produce a new snapshot version is not detectable without re-running
    the very resolver read this cache exists to skip -- no revision
    marker exists on the resolver/dependency service. Callers that
    observe such a change must call invalidate(); reconcile() also
    keeps its own trust gate ahead of the cache. If trust_service is
    wired here AND on the reconciliation service, a hit validates trust
    twice -- wire it on only one when cost matters.

    get() never alters recovery state (Rule): it reads through the
    existing services and the cache store; a miss never evicts or
    recomputes anything (stale entries are simply overwritten by the next
    put()). put()/invalidate() are idempotent: an identical put() keeps
    the original entry untouched, and invalidate() of an absent entry is
    a reported no-op.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        version_service=None,
        trust_service=None,
        integrity_service=None,
        store: AgentTaskRecoveryPreflightDependencyImpactCacheStore = None,
        metrics_service=None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightDependencySnapshotService;
                pass the real instance holding a task's actual snapshots
                or every get() misses.
            version_service: Optional Commit #3 version service (duck-
                typed, only latest_version() is called); when given,
                entries must carry an exact version number.
            trust_service: Optional Commit #6 trust service (duck-typed,
                only validate() is called); takes priority over
                integrity_service.
            integrity_service: Optional Commit #4 integrity service (duck-
                typed, only verify() is called).
            store: Defaults to a fresh in-memory store.
            metrics_service: Optional #4 metrics service (duck-typed,
                record_hit()/record_miss()/record_invalidation() only).
                get() and invalidate() report to it; every failure there
                is swallowed, so metrics can never change a lookup or an
                invalidation. peek() is never recorded.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._version_service = version_service
        self._trust_service = trust_service
        self._integrity_service = integrity_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightDependencyImpactCacheStore()
        self._metrics_service = metrics_service

    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotReconciliation]:
        """The cached impact result for task_id's exact preflight_id, or
        None on a miss: nothing cached, the entry's snapshot/version is no
        longer current, or trust/integrity validation fails. This is the
        validation path's lookup, so it is the one reported to metrics.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        result, miss_reason = self._lookup(task_id, preflight_id)
        if self._metrics_service is not None:
            try:
                if miss_reason is None:
                    self._metrics_service.record_hit(task_id, preflight_id)
                else:
                    self._metrics_service.record_miss(task_id, preflight_id, miss_reason)
            except Exception:
                pass  # metrics must never change a lookup result
        return result

    def peek(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotReconciliation]:
        """get() without reporting to metrics -- for callers (warming) whose
        own lookups are not validation-path traffic and would distort the
        hit/miss figures.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._lookup(task_id, preflight_id)[0]

    def _lookup(self, task_id: str, preflight_id: str) -> tuple:
        """(result, miss_reason) -- exactly one of them is None."""
        entry = self._store.get(task_id, preflight_id)
        if entry is None:
            return None, MISS_NOT_CACHED
        if self._current_identity(task_id, preflight_id) != (entry.snapshot_id, entry.version):
            return None, MISS_STALE
        if not self._is_trusted(task_id, entry.snapshot_id):
            return None, MISS_UNTRUSTED
        return entry.result, None

    def list_entries(self, task_id: str) -> list:
        """Every entry currently cached for task_id, oldest first -- a pure
        read that applies no staleness/trust check (that is get()'s job),
        for the invalidation service to decide which entries a change
        affects.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    def is_current(self, entry: AgentTaskRecoveryPreflightDependencyImpactCacheEntry) -> bool:
        """Whether entry's (snapshot_id, version) is still its preflight's
        current identity -- the same check get() applies, exposed so the
        invalidation service never re-derives version identity itself."""
        return self._current_identity(entry.task_id, entry.preflight_id) == (entry.snapshot_id, entry.version)

    def put(
        self, task_id: str, preflight_id: str, impact_result: AgentTaskRecoveryPreflightDependencySnapshotReconciliation
    ) -> Optional[AgentTaskRecoveryPreflightDependencyImpactCacheEntry]:
        """Cache impact_result for task_id's exact preflight_id. Returns
        the stored entry, or None when the result is not cacheable: it is
        unreliable, is not for the CURRENT snapshot/version, or (with a
        version service) carries no version. Idempotent: re-putting an
        identical result (ignoring reconciled_at) returns the original
        entry unchanged. An existing entry for the same snapshot/version
        computed LATER than impact_result is likewise returned unchanged:
        older evidence never replaces newer.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id/preflight_id is not a non-empty string, or
                impact_result is not a reconciliation result for exactly
                task_id/preflight_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        if (
            not isinstance(impact_result, AgentTaskRecoveryPreflightDependencySnapshotReconciliation)
            or impact_result.task_id != task_id
            or impact_result.preflight_id != preflight_id
        ):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError(
                f"impact_result must be a reconciliation result for task_id {task_id!r}, preflight_id {preflight_id!r}"
            )

        if not impact_result.reliable:
            return None
        if self._current_identity(task_id, preflight_id) != (impact_result.snapshot_id, impact_result.version):
            return None

        existing = self._store.get(task_id, preflight_id)
        if (
            existing is not None
            and existing.snapshot_id == impact_result.snapshot_id
            and existing.version == impact_result.version
            and existing.result.reconciled_at > impact_result.reconciled_at
        ):
            return existing  # never overwrite newer evidence for the same snapshot with older
        if (
            existing is not None
            and existing.snapshot_id == impact_result.snapshot_id
            and existing.version == impact_result.version
            and replace(impact_result, reconciled_at=existing.result.reconciled_at) == existing.result
        ):
            return existing

        return self._store.save(
            AgentTaskRecoveryPreflightDependencyImpactCacheEntry(
                task_id=task_id, preflight_id=preflight_id, snapshot_id=impact_result.snapshot_id,
                version=impact_result.version, result=impact_result, cached_at=self._now(),
            )
        )

    def invalidate(
        self, task_id: str, preflight_id: str, reason: str = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheInvalidation:
        """Drop task_id's cached impact for preflight_id, if any.
        Idempotent: `invalidated` is True only when this call removed an
        entry.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id/preflight_id is not a non-empty string, or reason
                is given and is not a string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        if reason is not None and not isinstance(reason, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError("reason must be a string when given")

        removed = self._store.delete(task_id, preflight_id)
        if removed and self._metrics_service is not None:
            try:
                self._metrics_service.record_invalidation(task_id, preflight_id, reason or None)
            except Exception:
                pass  # metrics must never change an invalidation
        return AgentTaskRecoveryPreflightDependencyImpactCacheInvalidation(
            task_id=task_id, preflight_id=preflight_id, invalidated=removed,
            reason=reason, invalidated_at=self._now(),
        )

    def evict(self, task_id: str, preflight_id: str) -> bool:
        """Remove task_id's entry for preflight_id as housekeeping, not as
        a reaction to a change: unlike invalidate() it is not reported to
        metrics as an invalidation. True only when this call removed one;
        idempotent.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError: If
                task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._store.delete(task_id, preflight_id)

    def _current_identity(self, task_id: str, preflight_id: str) -> Optional[tuple]:
        """(snapshot_id, version) of task_id/preflight_id's current
        snapshot -- None when there is none."""
        if self._version_service is not None:
            latest = self._version_service.latest_version(task_id, preflight_id)
            return (latest.snapshot_id, latest.version) if latest is not None else None
        latest = self._snapshot_service.latest_for_preflight(task_id, preflight_id)
        return (latest.snapshot_id, None) if latest is not None else None

    def _is_trusted(self, task_id: str, snapshot_id: str) -> bool:
        try:
            if self._trust_service is not None:
                return bool(self._trust_service.validate(task_id, snapshot_id).trusted)
            if self._integrity_service is not None:
                return bool(self._integrity_service.verify(task_id, snapshot_id).valid)
        except Exception:
            return False  # fail closed: unverifiable is never trusted
        return True

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError(
                f"{field_name} is required and must be a non-empty string"
            )
