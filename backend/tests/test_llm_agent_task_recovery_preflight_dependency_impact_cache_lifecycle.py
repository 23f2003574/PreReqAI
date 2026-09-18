import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventService
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    LIFECYCLE_EVICTED,
    LIFECYCLE_FAILED,
    LIFECYCLE_NONE,
    LIFECYCLE_REFRESHED,
    LIFECYCLE_UNAVAILABLE,
    UNCHANGED,
    IMPACT_CACHE_EVICTED_EVENT_TYPE,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService,
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


def _complete(lifecycle_service, task):
    for target in (PLANNED, TASK_READY, RUNNING, COMPLETED):
        lifecycle_service.transition(task.task_id, target)


def _new_preflight(preflight_store, task_id, decision=ALLOW):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=decision, blocking_reasons=(),
        warnings=(f"run-{next(_counter)}",), checked_at=NOW + timedelta(microseconds=next(_counter)),
    )
    return preflight_store.save(result).preflight_id


def _stack():
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
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service, trust_service=trust_service
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service, impact_cache_service=cache
    )
    analyses = []
    original = reconciliation_service.reconcile
    reconciliation_service.reconcile = lambda *a, **k: (analyses.append(a[1]), original(*a, **k))[1]
    consistency = LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService(
        cache_service=cache, snapshot_service=snapshot_service, reconciliation_service=reconciliation_service,
        preflight_store=preflight_store,
    )
    history_store = InMemoryAgentTaskEventStore()
    refresh = LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService(
        cache_service=cache, consistency_service=consistency, reconciliation_service=reconciliation_service,
        event_service=LLMAgentTaskEventService(history_store),
    )
    warming = LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService(
        cache_service=cache, reconciliation_service=reconciliation_service, snapshot_service=snapshot_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
        version_service=version_service, trust_service=trust_service,
    )
    invalidation_history = InMemoryAgentTaskEventStore()
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service,
        event_service=LLMAgentTaskEventService(invalidation_history),
    )
    batch = LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService(
        warming_service=warming, refresh_service=refresh, cache_service=cache, invalidation_service=invalidation
    )
    batch_refresh = LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshService(
        batch_reconciliation_service=batch, refresh_service=refresh
    )
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    cache._metrics_service = metrics
    evict_invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, preflight_store=preflight_store,
        preflight_invalidation_service=preflight_invalidation_service,
    )
    eviction = LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService(
        cache_service=cache, invalidation_service=evict_invalidation, event_service=LLMAgentTaskEventService(history_store)
    )
    batch_eviction = LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService(eviction_service=eviction)
    maintenance = LLMAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleService(
        warming_service=warming, batch_reconciliation_service=batch, batch_refresh_service=batch_refresh,
        batch_eviction_service=batch_eviction, metrics_service=metrics,
    )
    return {
        "maintenance": maintenance, "metrics": metrics, "batch_eviction": batch_eviction, "batch_refresh": batch_refresh,
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "preflight_invalidation_service": preflight_invalidation_service,
        "cache": cache, "refresh": refresh, "warming": warming, "batch": batch,
        "history_store": history_store, "invalidation_history": invalidation_history, "analyses": analyses,
    }


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def _new_task(s):
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    return task, dep


def _add_preflight(s, task, cached=True, decision=ALLOW):
    """Another preflight for task (which supersedes the previous one), with a snapshot and, optionally, a cached entry."""
    preflight_id = _new_preflight(s["preflight_store"], task.task_id, decision)
    snapshot = _snapshot(s, task, preflight_id)
    if cached:
        plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
            snapshot_service=s["snapshot_service"], version_service=s["version_service"]
        )
        s["cache"].put(task.task_id, preflight_id, plain.reconcile(task.task_id, snapshot.snapshot_id))
    s["analyses"].clear()
    return preflight_id, snapshot


def _entry(s, task, preflight_id):
    return next((e for e in s["cache"].list_entries(task.task_id) if e.preflight_id == preflight_id), None)


def _untrust(s, snapshot):
    s["trust_service"].validate(snapshot.task_id, snapshot.snapshot_id)  # integrity baseline
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def _actions(result):
    return {a.preflight_id: a.action for a in result.actions}


def _counts(result):
    return (result.none_count, result.refreshed_count, result.evicted_count, result.unavailable_count, result.failed_count)


def _superseded(s, task, n=2):
    """n older preflights, each with a cached entry, made obsolete by a later current one."""
    return [_add_preflight(s, task)[0] for _ in range(n)]


def test_all_current():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    entry = _entry(s, task, current)

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_NONE} and _counts(result) == (1, 0, 0, 0, 0)
    assert result.total == 1 and result.phase_errors == () and result.refresh is None  # nothing refreshable: not even called
    assert s["analyses"] == [] and _entry(s, task, current) == entry


def test_refresh_needed():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    newer = _snapshot(s, task, current)

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_REFRESHED} and _counts(result) == (0, 1, 0, 0, 0)
    action = result.actions[0]
    assert action.classification == "stale" and action.refresh_status == "refreshed"
    assert _entry(s, task, current).snapshot_id == newer.snapshot_id and s["cache"].get(task.task_id, current) is not None


def test_eviction_needed():
    s = _stack()
    task, _ = _new_task(s)
    old_one, old_two = _superseded(s, task)
    current, _ = _add_preflight(s, task)
    current_entry = _entry(s, task, current)

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {old_one: LIFECYCLE_EVICTED, old_two: LIFECYCLE_EVICTED, current: LIFECYCLE_NONE}
    assert _counts(result) == (1, 0, 2, 0, 0)
    assert _entry(s, task, old_one) is None and _entry(s, task, old_two) is None
    assert _entry(s, task, current) == current_entry  # the current valid entry survives
    assert len(s["history_store"].all()) == 2 and all(e.event_type == IMPACT_CACHE_EVICTED_EVENT_TYPE for e in s["history_store"].all())


def test_mixed_states_in_one_pass():
    s = _stack()
    task, _ = _new_task(s)
    old_one, old_two = _superseded(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)  # the current entry is stale

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_REFRESHED, old_one: LIFECYCLE_EVICTED, old_two: LIFECYCLE_EVICTED}
    assert _counts(result) == (0, 1, 2, 0, 0) and result.total == 3
    assert [a.preflight_id for a in result.actions] == sorted(_actions(result))  # deterministic order
    assert _entry(s, task, current).version == 2 and s["cache"].get(task.task_id, current) is not None


def test_trust_failure_never_consumes_the_snapshot_but_other_work_proceeds():
    s = _stack()
    task, _ = _new_task(s)
    old, = _superseded(s, task, 1)
    current, snapshot = _add_preflight(s, task)
    _untrust(s, snapshot)
    entry = _entry(s, task, current)

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_UNAVAILABLE, old: LIFECYCLE_EVICTED}
    assert s["analyses"] == []  # the untrusted snapshot was never analysed
    assert _entry(s, task, current) == entry and s["cache"].get(task.task_id, current) is None  # left non-consumable


def test_untrusted_snapshot_without_an_entry_is_never_fabricated():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task, cached=False)
    _untrust(s, snapshot)

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_UNAVAILABLE} and s["cache"].list_entries(task.task_id) == []


def test_refresh_phase_failure_is_reported_and_eviction_still_runs():
    s = _stack()
    task, _ = _new_task(s)
    old, = _superseded(s, task, 1)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    s["batch_refresh"].refresh = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("refresh phase down"))

    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_FAILED, old: LIFECYCLE_EVICTED}
    assert result.phase_errors == (("refresh", "refresh phase down"),) and result.refresh is None
    assert "refresh phase down" in next(a for a in result.actions if a.preflight_id == current).reasons[0]
    failed = next(a for a in result.actions if a.preflight_id == current)
    assert failed.eviction_status == "evicted"  # the stale, unconsumable entry was still removed as obsolete
    assert _entry(s, task, old) is None and _entry(s, task, current) is None  # the successful evictions were kept


def test_item_failure_inside_a_phase_is_isolated():
    s = _stack()
    task, _ = _new_task(s)
    old_one, old_two = _superseded(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    real = s["cache"].evict

    def flaky(task_id, preflight_id):
        if preflight_id == old_one:
            raise RuntimeError("store offline")
        return real(task_id, preflight_id)

    s["cache"].evict = flaky
    result = s["maintenance"].maintain(task.task_id)

    assert _actions(result) == {current: LIFECYCLE_REFRESHED, old_one: LIFECYCLE_FAILED, old_two: LIFECYCLE_EVICTED}
    assert result.phase_errors == () and _counts(result) == (0, 1, 1, 0, 1)
    assert _entry(s, task, old_one) is not None and _entry(s, task, current).version == 2  # successes preserved


def test_identify_and_reconcile_failures_do_not_stop_eviction():
    s = _stack()
    task, _ = _new_task(s)
    old, = _superseded(s, task, 1)
    current, _ = _add_preflight(s, task)
    s["warming"].active_preflight_ids = lambda task_id: (_ for _ in ()).throw(RuntimeError("store unreadable"))

    identify = s["maintenance"].maintain(task.task_id)

    assert [phase for phase, _ in identify.phase_errors] == ["identify"]
    assert identify.evicted_count == 1 and _entry(s, task, old) is None

    s["batch"].plan = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("plan down"))
    reconcile = s["maintenance"].maintain(task.task_id, [current])
    assert [phase for phase, _ in reconcile.phase_errors] == ["reconcile"] and reconcile.plan is None


def test_repeated_maintenance_is_idempotent():
    s = _stack()
    task, _ = _new_task(s)
    _superseded(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    first = s["maintenance"].maintain(task.task_id)
    entries = s["cache"].list_entries(task.task_id)
    analyses, events = len(s["analyses"]), len(s["history_store"].all())
    second = s["maintenance"].maintain(task.task_id)
    third = s["maintenance"].maintain(task.task_id)

    assert (first.refreshed_count, first.evicted_count) == (1, 2)
    for repeat in (second, third):
        assert set(_actions(repeat).values()) == {LIFECYCLE_NONE} and current in _actions(repeat)  # cleaned ones: nothing to do
        assert repeat.phase_errors == () and _counts(repeat) == (repeat.total, 0, 0, 0, 0)
    assert s["cache"].list_entries(task.task_id) == entries
    assert len(s["analyses"]) == analyses and len(s["history_store"].all()) == events


def test_valid_entries_and_history_are_preserved():
    s = _stack()
    task, dep = _new_task(s)
    old, = _superseded(s, task, 1)
    current, _ = _add_preflight(s, task)
    valid_entry = _entry(s, task, current)

    def state():
        return (
            s["preflight_store"].history(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            [s["version_service"].list_versions(task.task_id, p) for p in (old, current)],
            s["preflight_invalidation_service"].get_invalidation(current),
        )

    before = state()
    s["maintenance"].maintain(task.task_id)

    assert _entry(s, task, current) == valid_entry  # never replaced, never touched
    assert state() == before  # snapshots, versions, preflight records: exactly as they were
    (event,) = s["history_store"].all()  # only the eviction's own audit event
    assert event.payload["preflight_id"] == old


def test_recovery_behaviour_is_untouched():
    s = _stack()
    task, dep = _new_task(s)
    _superseded(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    dep_state = s["lifecycle_service"].get(dep.task_id).current_state

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state, s["lifecycle_service"].get(dep.task_id).current_state,
            s["dependency_service"].get_dependencies(task.task_id), s["preflight_store"].history(task.task_id),
        )

    before = state()
    s["maintenance"].maintain(task.task_id)
    s["maintenance"].maintain(task.task_id)

    assert state() == before and s["lifecycle_service"].get(dep.task_id).current_state == dep_state
    # the normal validation path still answers correctly from the maintained cache
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"], impact_cache_service=s["cache"]
    )
    latest = s["snapshot_service"].latest_for_preflight(task.task_id, current)
    assert plain.reconcile(task.task_id, latest.snapshot_id).status == UNCHANGED


def test_newer_cache_entries_are_never_overwritten():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["cache"]._store._entries[(task.task_id, current)] = replace(_entry(s, task, current), version=5)  # cache is ahead
    entry = _entry(s, task, current)

    result = s["maintenance"].maintain(task.task_id)

    assert s["analyses"] == [] and _entry(s, task, current) == entry  # neither refreshed over nor evicted
    assert _actions(result) == {current: LIFECYCLE_NONE} and result.evicted_count == 0
    assert s["cache"].get(task.task_id, current) is None  # unverifiable, so still never served


def test_metrics_are_attached_read_only_and_export_is_not_part_of_maintenance():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["cache"].get(task.task_id, current)  # one real, recorded lookup
    lookups = s["metrics"].summary(task.task_id).lookups

    result = s["maintenance"].maintain(task.task_id)
    without_metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleService(
        warming_service=s["warming"], batch_reconciliation_service=s["batch"],
        batch_refresh_service=s["batch_refresh"], batch_eviction_service=s["batch_eviction"],
    ).maintain(task.task_id)

    assert result.metrics.task_id == task.task_id and result.metrics.hits == 1
    assert s["metrics"].summary(task.task_id).lookups == lookups  # maintenance recorded no lookups of its own
    assert without_metrics.metrics is None
    parameters = LLMAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleService.__init__.__code__.co_varnames
    assert not any("export" in name for name in parameters)  # export stays an explicit, separate capability
    assert not any("export" in name for name in result.__dataclass_fields__)


def test_explicit_preflight_ids_limit_the_pass():
    s = _stack()
    task, _ = _new_task(s)
    old_one, old_two = _superseded(s, task)
    current, _ = _add_preflight(s, task)

    result = s["maintenance"].maintain(task.task_id, [old_one, "no-such-preflight", old_one])

    assert result.requested_preflight_ids == (old_one, "no-such-preflight")
    assert _actions(result) == {old_one: LIFECYCLE_EVICTED, "no-such-preflight": LIFECYCLE_NONE}  # nothing to maintain
    assert _entry(s, task, old_two) is not None and _entry(s, task, current) is not None  # not requested: untouched


def test_task_without_anything_is_an_empty_result():
    s = _stack()

    result = s["maintenance"].maintain("unknown-task")

    assert result.actions == () and result.total == 0 and _counts(result) == (0, 0, 0, 0, 0) and result.phase_errors == ()


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["maintenance"].maintain(bad)
    with pytest.raises(Error):
        s["maintenance"].maintain("task", "not-a-list")
    with pytest.raises(Error):
        s["maintenance"].maintain("task", ["ok", ""])
