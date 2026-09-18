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
    BATCH_CONSISTENT,
    BATCH_INVALIDATED,
    BATCH_REFRESHED,
    BATCH_UNAVAILABLE,
    IMPACT_CACHE_INVALIDATED_EVENT_TYPE,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService,
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
    return {
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


def _statuses(result):
    return {o.preflight_id: o.status for o in result.outcomes}


def _approve_all(s):
    """Only a task's latest preflight is eligible in real wiring; approve every one so a batch holds several."""
    s["warming"].eligibility = lambda task_id, preflight_id: ((), None, None)


def test_all_consistent_batch():
    s = _stack()
    task, _ = _new_task(s)
    first, _ = _add_preflight(s, task)
    second, _ = _add_preflight(s, task)
    third, _ = _add_preflight(s, task)
    _approve_all(s)
    entries = s["cache"].list_entries(task.task_id)

    result = s["batch"].reconcile(task.task_id, [first, second, third])

    assert (result.total, result.consistent_count) == (3, 3)
    assert (result.refreshed_count, result.invalidated_count, result.unavailable_count) == (0, 0, 0)
    assert all(o.status == BATCH_CONSISTENT and o.refresh_status == "current" for o in result.outcomes)
    assert s["analyses"] == [] and s["cache"].list_entries(task.task_id) == entries


def test_mixed_stale_and_current_entries():
    s = _stack()
    task, dep = _new_task(s)
    fresh, _ = _add_preflight(s, task)
    stale, _ = _add_preflight(s, task)
    missing, _ = _add_preflight(s, task, cached=False)
    _snapshot(s, task, stale)  # stale: a newer snapshot version exists
    _approve_all(s)
    fresh_entry = _entry(s, task, fresh)

    result = s["batch"].reconcile(task.task_id, [fresh, stale, missing])

    assert _statuses(result) == {fresh: BATCH_CONSISTENT, stale: BATCH_REFRESHED, missing: BATCH_REFRESHED}
    assert (result.consistent_count, result.refreshed_count) == (1, 2)
    assert _entry(s, task, fresh) == fresh_entry  # the consistent one was not touched
    assert _entry(s, task, stale).version == 2 and _entry(s, task, missing) is not None
    assert next(o for o in result.outcomes if o.preflight_id == stale).categories == ("stale",)


def test_active_run_invalidates_entries_of_superseded_preflights():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    current_entry = _entry(s, task, current)

    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_CONSISTENT, old: BATCH_INVALIDATED}
    assert [o.preflight_id for o in result.outcomes] == [current, old]
    assert _entry(s, task, old) is None and _entry(s, task, current) == current_entry
    assert "current preflight" in next(o for o in result.outcomes if o.preflight_id == old).reasons[0]
    (event,) = s["invalidation_history"].list_for_task(task.task_id)  # removal recorded through #2's history
    assert event.event_type == IMPACT_CACHE_INVALIDATED_EVENT_TYPE and event.payload["preflight_id"] == old


def test_invalid_snapshot_is_unavailable_and_the_cache_is_left_alone():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task)
    _untrust(s, snapshot)
    entry = _entry(s, task, current)

    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_UNAVAILABLE} and result.unavailable_count == 1
    assert "not trusted" in result.outcomes[0].reasons[0]
    assert s["analyses"] == [] and _entry(s, task, current) == entry
    assert s["cache"].get(task.task_id, current) is None  # still non-consumable


def test_untrusted_snapshot_without_an_entry_is_unavailable_not_fabricated():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task, cached=False)
    _untrust(s, snapshot)

    assert s["batch"].reconcile_active(task.task_id).unavailable_count == 1
    assert s["cache"].list_entries(task.task_id) == []


def test_preflight_without_snapshot_has_its_obsolete_entry_invalidated():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task)
    del s["snapshot_service"]._store._by_id[snapshot.snapshot_id]  # the source is gone
    s["version_service"]._store._by_preflight.clear()

    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_INVALIDATED} and _entry(s, task, current) is None


def test_partial_failure_preserves_successful_results():
    s = _stack()
    task, _ = _new_task(s)
    first, _ = _add_preflight(s, task)
    second, _ = _add_preflight(s, task)
    third, _ = _add_preflight(s, task)
    for preflight_id in (first, second, third):
        _snapshot(s, task, preflight_id)
    _approve_all(s)
    real = s["refresh"].refresh

    def flaky(task_id, preflight_id):
        if preflight_id == second:
            raise RuntimeError("resolver down")
        return real(task_id, preflight_id)

    s["refresh"].refresh = flaky
    result = s["batch"].reconcile(task.task_id, [first, second, third])

    assert [(o.preflight_id, o.status) for o in result.outcomes] == [
        (first, BATCH_REFRESHED), (second, BATCH_UNAVAILABLE), (third, BATCH_REFRESHED)
    ]
    assert "resolver down" in result.outcomes[1].reasons[0]
    assert (result.refreshed_count, result.unavailable_count) == (2, 1)
    assert _entry(s, task, first).version == 2 and _entry(s, task, third).version == 2
    assert _entry(s, task, second).version == 1  # left exactly as it was


def test_failing_invalidation_is_isolated_too():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    class _Broken:
        def invalidate_for_preflight(self, *a):
            raise RuntimeError("invalidation offline")

    s["batch"]._invalidation_service = _Broken()
    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_REFRESHED, old: BATCH_UNAVAILABLE}
    assert _entry(s, task, old) is not None  # a failed removal left it in place


def test_empty_batches():
    s = _stack()
    task, _ = _new_task(s)
    _add_preflight(s, task)

    explicit = s["batch"].reconcile(task.task_id, [])
    unknown = s["batch"].reconcile_active("task-without-preflights")

    for result in (explicit, unknown):
        assert result.outcomes == () and result.total == 0
        assert (result.consistent_count, result.refreshed_count, result.invalidated_count, result.unavailable_count) == (0,) * 4


def test_invalidated_preflights_are_excluded_from_an_active_run():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    result = s["batch"].reconcile_active(task.task_id)

    assert result.excluded_preflight_ids == (current,) and result.outcomes == ()


def test_repeated_reconciliation_is_idempotent():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    first = s["batch"].reconcile_active(task.task_id)
    entries = s["cache"].list_entries(task.task_id)
    analyses, events = len(s["analyses"]), (len(s["history_store"].all()), len(s["invalidation_history"].all()))
    second = s["batch"].reconcile_active(task.task_id)
    third = s["batch"].reconcile_active(task.task_id)

    assert (first.refreshed_count, first.invalidated_count) == (1, 1)
    for repeat in (second, third):
        assert (repeat.refreshed_count, repeat.invalidated_count) == (0, 0)
        assert _statuses(repeat)[current] == BATCH_CONSISTENT
    assert s["cache"].list_entries(task.task_id) == entries and len(s["analyses"]) == analyses
    assert (len(s["history_store"].all()), len(s["invalidation_history"].all())) == events


def test_newer_cache_entries_are_preserved():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["cache"]._store._entries[(task.task_id, current)] = replace(_entry(s, task, current), version=5)  # cache is ahead
    entry = _entry(s, task, current)

    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_CONSISTENT} and result.outcomes[0].refresh_status == "newer_entry"
    assert s["analyses"] == [] and _entry(s, task, current) == entry


def test_newer_entry_written_during_reconciliation_is_never_overwritten():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    real = s["refresh"]._reconciliation_service.reconcile

    def racing(task_id, snapshot_id, **kwargs):
        result = real(task_id, snapshot_id, **kwargs)
        s["cache"].invalidate(task_id, current)
        s["cache"].put(
            task_id, current,
            replace(result, added=("raced",), status=CHANGED, reconciled_at=result.reconciled_at + timedelta(seconds=5)),
        )
        return result

    s["refresh"]._reconciliation_service = type("R", (), {"reconcile": staticmethod(racing)})()
    result = s["batch"].reconcile_active(task.task_id)

    assert _statuses(result) == {current: BATCH_CONSISTENT}
    assert _entry(s, task, current).result.added == ("raced",)


def test_explicit_ids_are_processed_in_order_without_duplicates():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)

    result = s["batch"].reconcile(task.task_id, [old, "no-such-preflight", current, old])

    assert [o.preflight_id for o in result.outcomes] == [old, "no-such-preflight", current]
    assert _statuses(result) == {old: BATCH_INVALIDATED, "no-such-preflight": BATCH_UNAVAILABLE, current: BATCH_CONSISTENT}
    assert result.total == 3 and result.consistent_count + result.invalidated_count + result.unavailable_count == 3


def test_reconciliation_never_touches_recovery_state_or_history_records():
    s = _stack()
    task, dep = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state, s["lifecycle_service"].get(dep.task_id).current_state,
            s["preflight_store"].history(task.task_id), s["dependency_service"].get_dependencies(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            s["version_service"].list_versions(task.task_id, current), s["version_service"].list_versions(task.task_id, old),
            s["preflight_invalidation_service"].get_invalidation(current),
        )

    before = state()
    s["batch"].reconcile_active(task.task_id)
    s["batch"].reconcile(task.task_id, [old, current])

    assert state() == before  # snapshots and version history are preserved exactly


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["batch"].reconcile(bad)
        with pytest.raises(Error):
            s["batch"].reconcile_active(bad)
    with pytest.raises(Error):
        s["batch"].reconcile("task", "not-a-list")
    with pytest.raises(Error):
        s["batch"].reconcile("task", ["ok", ""])
