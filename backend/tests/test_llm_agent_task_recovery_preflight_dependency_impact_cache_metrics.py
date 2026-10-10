import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import (
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    IMPACT_CACHE_METRIC_EVENT_TYPE,
    MISS_NOT_CACHED,
    MISS_STALE,
    MISS_UNTRUSTED,
    UNCHANGED,
    WARMED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_counter = itertools.count()


def _task(lifecycle_service):
    return lifecycle_service.create({"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"})


def _new_preflight(preflight_store, task_id):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=ALLOW, blocking_reasons=(),
        warnings=(f"run-{next(_counter)}",), checked_at=NOW + timedelta(microseconds=next(_counter)),
    )
    return preflight_store.save(result).preflight_id


def _stack(metrics=True):
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    version_service = LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService(snapshot_service=snapshot_service)
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(
        snapshot_service=snapshot_service, version_service=version_service
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service, version_service=version_service
    )
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    metrics_store = InMemoryAgentTaskEventStore()  # dedicated: the task stream stays untouched
    metrics_service = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService(
        event_service=LLMAgentTaskEventService(metrics_store), event_query_service=LLMAgentTaskEventQueryService(metrics_store)
    )
    active_metrics = metrics_service if metrics else None
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service, trust_service=trust_service,
        metrics_service=active_metrics,
    )
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, dependency_service=dependency_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service, impact_cache_service=cache,
        impact_cache_invalidation_service=invalidation, impact_cache_metrics_service=active_metrics,
    )
    warming = LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService(
        cache_service=cache, reconciliation_service=reconciliation_service, snapshot_service=snapshot_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
        version_service=version_service, invalidation_service=invalidation, metrics_service=active_metrics,
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "cache": cache, "invalidation": invalidation,
        "reconciliation_service": reconciliation_service, "warming": warming,
        "metrics": metrics_service, "metrics_store": metrics_store,
    }


def _prepared(s):
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    return task, preflight_id, _snapshot(s, task, preflight_id)


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def _result(s, task, snapshot):
    """A reliable impact result computed without touching the cache."""
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )
    return plain.reconcile(task.task_id, snapshot.snapshot_id)


def test_hit_and_miss_recorded_from_real_lookups():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)

    assert s["cache"].get(task.task_id, preflight_id) is None  # miss: not cached
    s["cache"].put(task.task_id, preflight_id, _result(s, task, snapshot))
    assert s["cache"].get(task.task_id, preflight_id) is not None  # hit
    assert s["cache"].get(task.task_id, preflight_id) is not None  # hit

    m = s["metrics"].summary(task.task_id)
    assert (m.hits, m.misses, m.lookups) == (2, 1, 3)
    assert m.miss_reasons == {MISS_NOT_CACHED: 1}
    assert m.hit_rate == pytest.approx(2 / 3)
    assert m.miss_rate == pytest.approx(1 / 3)


def test_stale_entry_is_recorded_as_stale_miss():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["cache"].put(task.task_id, preflight_id, _result(s, task, snapshot))
    _snapshot(s, task, preflight_id)  # replaces the snapshot the entry is bound to

    assert s["cache"].get(task.task_id, preflight_id) is None

    m = s["metrics"].summary(task.task_id)
    assert (m.hits, m.misses, m.stale_misses) == (0, 1, 1)
    assert m.miss_reasons == {MISS_STALE: 1}


def test_untrusted_entry_is_recorded_as_untrusted_miss():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # integrity baseline
    s["cache"].put(task.task_id, preflight_id, _result(s, task, snapshot))
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    assert s["cache"].get(task.task_id, preflight_id) is None

    m = s["metrics"].summary(task.task_id)
    assert m.miss_reasons == {MISS_UNTRUSTED: 1}
    assert m.stale_misses == 0


def test_invalidations_recorded_only_for_real_removals():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["cache"].put(task.task_id, preflight_id, _result(s, task, snapshot))

    s["cache"].invalidate(task.task_id, preflight_id, reason="dependency changed")
    s["cache"].invalidate(task.task_id, preflight_id, reason="dependency changed")  # already gone
    s["cache"].invalidate(task.task_id, "never-cached")

    assert s["metrics"].summary(task.task_id).invalidations == 1


def test_invalidation_service_removals_are_counted_once_each():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["cache"].put(task.task_id, preflight_id, _result(s, task, snapshot))

    s["invalidation"].invalidate_for_preflight(task.task_id, preflight_id)
    s["invalidation"].invalidate_for_preflight(task.task_id, preflight_id)

    assert s["metrics"].summary(task.task_id).invalidations == 1


def test_warming_recorded_and_its_lookups_do_not_distort_hit_rate():
    s = _stack()
    task, preflight_id, _ = _prepared(s)

    assert s["warming"].warm(task.task_id, preflight_id).status == WARMED
    s["warming"].warm(task.task_id, preflight_id)  # already current: not an attempt

    m = s["metrics"].summary(task.task_id)
    assert (m.warm_attempts, m.warm_successes, m.warm_failures) == (1, 1, 0)
    assert m.warm_success_rate == 1.0
    assert (m.hits, m.misses, m.lookups) == (0, 0, 0)  # warming uses peek(), never a recorded lookup


def test_failed_warming_recorded_as_failure():
    s = _stack()
    task, preflight_id, _ = _prepared(s)
    s["warming"]._reconciliation_service = type(
        "R", (), {"reconcile": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("resolver down"))}
    )()

    s["warming"].warm(task.task_id, preflight_id)

    m = s["metrics"].summary(task.task_id)
    assert (m.warm_attempts, m.warm_successes, m.warm_failures) == (1, 0, 1)
    assert m.warm_success_rate == 0.0


def test_skipped_warming_is_not_an_attempt():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)  # no snapshot: ineligible

    s["warming"].warm(task.task_id, preflight_id)

    assert s["metrics"].summary(task.task_id).warm_attempts == 0


def test_computations_avoided_counts_only_consumed_cache_hits():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)

    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)  # miss -> fresh, stored
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)  # hit, consumed
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)  # hit, consumed
    m = s["metrics"].summary(task.task_id)
    assert (m.hits, m.misses, m.computations_avoided) == (2, 1, 2)

    newer = _snapshot(s, task, preflight_id)
    s["reconciliation_service"].reconcile(task.task_id, newer.snapshot_id)
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)  # hit, but for the newer snapshot: discarded
    m = s["metrics"].summary(task.task_id)
    assert m.hits == 3 and m.computations_avoided == 2  # a hit that was not used avoided nothing


def test_warmed_entry_is_consumed_by_normal_validation_path():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["warming"].warm(task.task_id, preflight_id)

    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED

    m = s["metrics"].summary(task.task_id)
    assert (m.warm_successes, m.hits, m.computations_avoided) == (1, 1, 1)


def test_summary_calculations_from_direct_records():
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    for _ in range(3):
        metrics.record_hit("t", "p")
    metrics.record_miss("t", "p", MISS_STALE)
    metrics.record_miss("t", "p", MISS_NOT_CACHED)
    metrics.record_miss("t", "p", MISS_NOT_CACHED)
    metrics.record_miss("t", "p", "some-other-reason")
    metrics.record_invalidation("t", "p", "changed")
    metrics.record_invalidation("t", "p")
    for success in (True, True, False, True):
        metrics.record_warm("t", "p", success)
    metrics.record_computation_avoided("t", "p")

    m = metrics.summary("t")

    assert (m.hits, m.misses, m.lookups) == (3, 4, 7)
    assert m.hit_rate == pytest.approx(3 / 7) and m.miss_rate == pytest.approx(4 / 7)
    assert m.stale_misses == 1
    assert m.miss_reasons == {MISS_NOT_CACHED: 2, MISS_STALE: 1, "some-other-reason": 1}
    assert m.invalidations == 2
    assert (m.warm_attempts, m.warm_successes, m.warm_failures) == (4, 3, 1)
    assert m.warm_success_rate == pytest.approx(0.75)
    assert m.computations_avoided == 1


def test_empty_summary_is_all_zero():
    m = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService().summary("unseen-task")

    assert (m.hits, m.misses, m.lookups, m.invalidations, m.warm_attempts, m.computations_avoided) == (0,) * 6
    assert (m.hit_rate, m.miss_rate, m.warm_success_rate) == (0.0, 0.0, 0.0)
    assert m.miss_reasons == {}


def test_repeated_recording_counts_every_occurrence_and_summary_is_stable():
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()

    for _ in range(5):
        metrics.record_hit("t", "p")

    first, second = metrics.summary("t"), metrics.summary("t")
    assert first.hits == second.hits == 5
    assert (first.hit_rate, first.lookups) == (second.hit_rate, second.lookups) == (1.0, 5)
    assert len(metrics._event_service.store.list_for_task("t")) == 5  # summary() wrote nothing


def test_metrics_are_scoped_per_task():
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    metrics.record_hit("task-a", "p")
    metrics.record_miss("task-b", "p", MISS_NOT_CACHED)

    assert (metrics.summary("task-a").hits, metrics.summary("task-a").misses) == (1, 0)
    assert (metrics.summary("task-b").hits, metrics.summary("task-b").misses) == (0, 1)


def test_metrics_never_change_raw_cache_state_or_results():
    with_metrics, without = _stack(metrics=True), _stack(metrics=False)
    outcomes = []
    for s in (with_metrics, without):
        task, preflight_id, snapshot = _prepared(s)
        s["cache"].get(task.task_id, preflight_id)
        s["warming"].warm(task.task_id, preflight_id)
        result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
        entries = s["cache"].list_entries(task.task_id)
        outcomes.append((result.status, result.version, [(e.snapshot_id, e.version) for e in entries]))

    assert outcomes[0][0] == outcomes[1][0]
    assert outcomes[0][1] == outcomes[1][1]
    assert [v for _, v in outcomes[0][2]] == [v for _, v in outcomes[1][2]]
    assert with_metrics["metrics"].summary(list(with_metrics["metrics_store"].all())[0].task_id).lookups >= 1


class _BrokenMetrics:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RuntimeError("metrics backend offline")
        return fail


class _BrokenEventService:
    store = InMemoryAgentTaskEventStore()

    def emit(self, *args, **kwargs):
        raise RuntimeError("event store offline")


def test_metrics_failure_never_breaks_cache_lookup_or_invalidation():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    s["cache"]._metrics_service = _BrokenMetrics()
    result = _result(s, task, snapshot)

    assert s["cache"].get(task.task_id, preflight_id) is None
    assert s["cache"].put(task.task_id, preflight_id, result) is not None
    assert s["cache"].get(task.task_id, preflight_id) == result
    assert s["cache"].invalidate(task.task_id, preflight_id).invalidated is True


def test_metrics_failure_never_breaks_warming_or_reconciliation():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    for service in (s["cache"], s["warming"], s["reconciliation_service"]):
        for attr in ("_metrics_service", "_impact_cache_metrics_service"):
            if hasattr(service, attr):
                setattr(service, attr, _BrokenMetrics())

    assert s["warming"].warm(task.task_id, preflight_id).status == WARMED
    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_real_metrics_service_with_failing_event_store_does_not_break_recovery():
    s = _stack()
    task, preflight_id, snapshot = _prepared(s)
    broken = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService(event_service=_BrokenEventService())
    for service in (s["cache"], s["warming"]):
        service._metrics_service = broken
    s["reconciliation_service"]._impact_cache_metrics_service = broken

    assert s["warming"].warm(task.task_id, preflight_id).status == WARMED
    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED
    assert s["cache"].invalidate(task.task_id, preflight_id).invalidated is True


def test_metric_events_use_their_own_event_type():
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    metrics.record_hit("t", "p")

    (event,) = metrics._event_service.store.list_for_task("t")
    assert event.event_type == IMPACT_CACHE_METRIC_EVENT_TYPE
    assert event.payload == {"metric": "hit", "preflight_id": "p"}


def test_validation():
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            metrics.record_hit(bad, "p")
        with pytest.raises(Error):
            metrics.record_hit("t", bad)
        with pytest.raises(Error):
            metrics.summary(bad)
    with pytest.raises(Error):
        metrics.record_miss("t", "p", "")
    with pytest.raises(Error):
        metrics.record_invalidation("t", "p", 5)
    for bad in ("yes", 1, None):
        with pytest.raises(Error):
            metrics.record_warm("t", "p", bad)
