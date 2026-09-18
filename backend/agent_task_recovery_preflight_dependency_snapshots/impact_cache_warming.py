from datetime import datetime, timezone
from typing import Optional

from backend.agent_policy_engine import DENY

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult,
    AgentTaskRecoveryPreflightDependencyImpactCacheWarmSummary,
)
from .reconciliation import LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService

WARMED = "warmed"
ALREADY_CURRENT = "already_current"
SKIPPED = "skipped"
NOT_CACHED = "not_cached"
WARM_STATUSES = frozenset({WARMED, ALREADY_CURRENT, SKIPPED, NOT_CACHED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError(ValueError):
    """Raised when warm()/warm_active() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService:
    """Pre-computes the dependency-impact result for a task's current
    recovery preflight, so the normal validation path (reconcile() with
    the #1 cache) finds it already stored -- never a background-job,
    worker or queue framework (Rule): warm()/warm_active() are plain
    synchronous calls, and whoever schedules them (a caller, cron,
    a test) owns the cadence. Nothing here loops, retries, or defers.

    Every step reuses an existing service: the analysis is Commit #2's
    own reconcile() (Rule: "Resolve impact through the existing
    dependency-impact analysis service"), the storage is #1's cache
    put(), stale entries are removed by #2's invalidation service, and
    eligibility comes from the preflight store, the guardrails' own
    invalidation/freshness services, and the snapshot trust/integrity
    services. This class computes no dependency state itself.

    warm() writes only when ALL of the following hold, checked in order,
    and reports SKIPPED with every reason it can establish otherwise:
      1. the preflight is recorded for task_id;
      2. it is task_id's CURRENT preflight (a superseded one is never
         warmed -- it is not actionable);
      3. it has not been explicitly invalidated;
      4. its decision is not DENY (an impact result for a preflight
         recovery can never use is wasted work);
      5. a freshness_service, when given, reports it fresh;
      6. it has a dependency snapshot (warming NEVER captures one --
         capturing is a write to the dependency record, not a cache
         concern) whose identity is the latest via the version service,
         or the snapshot service without one;
      7. that snapshot is trusted (trust_service, else integrity_service
         -- the same precedence the cache uses). With neither configured
         there is no trust gate, exactly as in the cache and
         reconciliation services.
    Then, when an invalidation_service is configured, it runs first so a
    change signalled since the entry was computed removes it; an existing
    entry that survives get() (current identity, still trusted) is left
    alone as ALREADY_CURRENT -- "skip unchanged valid entries". Otherwise
    the impact is analysed and stored: WARMED, with replaced=True if a
    stale entry existed. If the invalidation pass itself fails, the
    existing entry is not relied on and is recomputed.

    Never overwrites newer evidence (Rule): cache.put() refuses a result
    whose snapshot is no longer current and keeps an existing entry for
    the same snapshot/version computed later than the new result; warm()
    reports the latter as ALREADY_CURRENT. That check-and-write is not
    atomic across processes -- the in-memory store this project ships is
    single-process.

    Idempotent (Rule): a second warm()/warm_active() over unchanged state
    finds every entry current and changes nothing.

    Read-only with respect to recovery/scheduling (Rule): no lifecycle,
    scheduling, authorization or dependency-mutating collaborator is held.
    The only writes are cache entries and the cache removals/history
    events #2's invalidation service already makes, plus the trust
    history append every trust validation makes.

    warm_active() processes the task's recorded preflights newest-first,
    excluding any that were explicitly invalidated. Because only the
    latest preflight can be current, at most one is ever warmed; older,
    superseded ones are reported SKIPPED without any analysis.
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService = None,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        preflight_store=None,
        preflight_invalidation_service=None,
        freshness_service=None,
        version_service=None,
        trust_service=None,
        integrity_service=None,
        invalidation_service=None,
        metrics_service=None,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the SAME
                instance the validation path reads from.
            reconciliation_service: Defaults to a fresh reconciliation
                service over snapshot_service; pass the real, wired one.
            snapshot_service: Defaults to a fresh one; pass the real one
                holding the task's snapshots.
            preflight_store: Required in practice, no default (a fresh
                empty store would find no preflight to warm): the
                LLMAgentTaskRecoveryPreflightStore holding task_id's
                preflights (get()/history() are called).
            preflight_invalidation_service: Optional, duck-typed
                (get_invalidation() only).
            freshness_service: Optional, duck-typed (check(task_id,
                preflight=...).is_fresh only).
            version_service: Optional, duck-typed (latest_version() only).
            trust_service: Optional, duck-typed (validate().trusted).
            integrity_service: Optional, duck-typed (verify().valid);
                used only when trust_service is absent.
            invalidation_service: Optional #2 invalidation service (duck-
                typed, reconcile() only).
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
        self._preflight_invalidation_service = preflight_invalidation_service
        self._freshness_service = freshness_service
        self._version_service = version_service
        self._trust_service = trust_service
        self._integrity_service = integrity_service
        self._invalidation_service = invalidation_service
        self._metrics_service = metrics_service

    def warm(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult:
        """Warm task_id's exact preflight_id if it is current, trusted and
        usable -- see the class docstring. Never raises for an ineligible
        preflight; that is a SKIPPED result.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError:
                If task_id or preflight_id is not a non-empty string, or
                no preflight_store was configured
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        self._require_store()
        return self._warm(task_id, preflight_id)

    def warm_active(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheWarmSummary:
        """Warm every currently relevant preflight recorded for task_id,
        newest first, excluding explicitly invalidated ones.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError:
                If task_id is not a non-empty string, or no
                preflight_store was configured
        """
        self._require_text(task_id, "task_id")
        self._require_store()

        results, excluded = [], []
        for record in reversed(self._preflight_store.history(task_id)):
            if self._invalidation_of(record.preflight_id) is not None:
                excluded.append(record.preflight_id)
                continue
            results.append(self._warm(task_id, record.preflight_id))

        def count(status):
            return sum(1 for result in results if result.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCacheWarmSummary(
            task_id=task_id, results=tuple(results), warmed_count=count(WARMED),
            already_current_count=count(ALREADY_CURRENT), skipped_count=count(SKIPPED),
            not_cached_count=count(NOT_CACHED), excluded_preflight_ids=tuple(excluded), warmed_at=self._now(),
        )

    def _warm(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult:
        result = self._warm_uncounted(task_id, preflight_id)
        if self._metrics_service is not None and result.status in (WARMED, NOT_CACHED):
            try:
                self._metrics_service.record_warm(task_id, preflight_id, result.status == WARMED)
            except Exception:
                pass  # metrics must never change a warming outcome
        return result

    def _warm_uncounted(
        self, task_id: str, preflight_id: str
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult:
        record = next((r for r in self._preflight_store.history(task_id) if r.preflight_id == preflight_id), None)
        if record is None:
            return self._result(task_id, preflight_id, SKIPPED, reasons=("no such preflight is recorded for this task",))

        current = self._preflight_store.get(task_id)
        if current is None or current.preflight_id != preflight_id:
            return self._result(task_id, preflight_id, SKIPPED, reasons=("preflight is no longer the task's current preflight",))

        invalidation = self._invalidation_of(preflight_id)
        if invalidation is not None:
            return self._result(task_id, preflight_id, SKIPPED, reasons=(f"preflight was invalidated: {invalidation.reason}",))

        if record.decision == DENY:
            return self._result(task_id, preflight_id, SKIPPED, reasons=("preflight decision is deny",))

        if self._freshness_service is not None:
            freshness = self._freshness_service.check(task_id, preflight=record)
            if not freshness.is_fresh:
                return self._result(
                    task_id, preflight_id, SKIPPED,
                    reasons=("preflight is stale: " + "; ".join(freshness.stale_reasons),),
                )

        identity = self._current_identity(task_id, preflight_id)
        if identity is None:
            return self._result(task_id, preflight_id, SKIPPED, reasons=("preflight has no dependency snapshot",))
        snapshot_id, version = identity

        trust_reasons = self._trust_failures(task_id, snapshot_id)
        if trust_reasons:
            return self._result(task_id, preflight_id, SKIPPED, snapshot_id, version, reasons=trust_reasons)

        # Read BEFORE the invalidation pass, which may remove the very entry being replaced.
        had_entry = any(entry.preflight_id == preflight_id for entry in self._cache_service.list_entries(task_id))
        if self._invalidation_service is not None:
            try:
                self._invalidation_service.reconcile(task_id)
            except Exception:
                pass  # staleness unknown: fall through and recompute rather than rely on an unchecked entry
        if self._cache_service.peek(task_id, preflight_id) is not None:  # not a validation-path lookup
            return self._result(task_id, preflight_id, ALREADY_CURRENT, snapshot_id, version, reasons=("a valid entry is already cached",))

        try:
            impact = self._reconciliation_service.reconcile(task_id, snapshot_id, use_cache=False)
        except Exception as error:
            return self._result(task_id, preflight_id, NOT_CACHED, snapshot_id, version, reasons=(f"impact analysis failed: {error}",))

        entry = self._cache_service.put(task_id, preflight_id, impact)
        if entry is None:
            reason = impact.reason if not impact.reliable else "snapshot/version was superseded while warming"
            return self._result(
                task_id, preflight_id, NOT_CACHED, snapshot_id, version, impact_status=impact.status, reasons=(reason,)
            )
        if entry.result.reconciled_at > impact.reconciled_at:
            return self._result(
                task_id, preflight_id, ALREADY_CURRENT, snapshot_id, version, impact_status=entry.result.status,
                reasons=("a newer entry was already cached and was kept",),
            )
        return self._result(
            task_id, preflight_id, WARMED, snapshot_id, version, replaced=had_entry, impact_status=impact.status
        )

    def _current_identity(self, task_id: str, preflight_id: str) -> Optional[tuple]:
        if self._version_service is not None:
            latest = self._version_service.latest_version(task_id, preflight_id)
            return (latest.snapshot_id, latest.version) if latest is not None else None
        latest = self._snapshot_service.latest_for_preflight(task_id, preflight_id)
        return (latest.snapshot_id, None) if latest is not None else None

    def _trust_failures(self, task_id: str, snapshot_id: str) -> tuple:
        try:
            if self._trust_service is not None:
                trust = self._trust_service.validate(task_id, snapshot_id)
                return () if trust.trusted else ("snapshot is not trusted: " + "; ".join(trust.blocking_reasons),)
            if self._integrity_service is not None:
                integrity = self._integrity_service.verify(task_id, snapshot_id)
                return () if integrity.valid else ("snapshot failed integrity verification: " + "; ".join(integrity.reasons),)
        except Exception as error:
            return (f"snapshot trust could not be verified: {error}",)  # fail closed
        return ()

    def _invalidation_of(self, preflight_id: str):
        if self._preflight_invalidation_service is None:
            return None
        return self._preflight_invalidation_service.get_invalidation(preflight_id)

    def _result(
        self, task_id, preflight_id, status, snapshot_id=None, version=None, replaced=False, impact_status=None, reasons=()
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult:
        return AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult(
            task_id=task_id, preflight_id=preflight_id, status=status, snapshot_id=snapshot_id, version=version,
            replaced=replaced, impact_status=impact_status, reasons=tuple(reasons), warmed_at=self._now(),
        )

    def _require_store(self) -> None:
        if self._preflight_store is None:
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError(
                "a preflight_store is required to determine which preflights are current"
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError(
                f"{field_name} is required and must be a non-empty string"
            )
