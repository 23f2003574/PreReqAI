import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import (
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_events.retention import DEFAULT_RETENTION_WINDOW
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    BATCH_EVICTED,
    BATCH_EVICTION_FAILED,
    BATCH_EVICTION_SKIPPED,
    EXPIRED_UNPROVABLE,
    IMPACT_CACHE_EVICTED_EVENT_TYPE,
    PROTECTED_VALID,
    PROTECTED_WITHIN_RETENTION,
    REPLACED_SINCE_PLAN,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheService,
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


def _stack(with_invalidation=True):
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
    task_event_store = InMemoryAgentTaskEventStore()
    task_event_service = LLMAgentTaskEventService(task_event_store)
    metrics = LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService()
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service, trust_service=trust_service,
        metrics_service=metrics,
    )
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, dependency_service=dependency_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
        event_query_service=LLMAgentTaskEventQueryService(task_event_store),
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service, impact_cache_service=cache,
        impact_cache_invalidation_service=invalidation,
    )
    history_store = InMemoryAgentTaskEventStore()
    eviction = LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService(
        cache_service=cache, invalidation_service=invalidation if with_invalidation else None,
        event_service=LLMAgentTaskEventService(history_store),
    )
    batch_eviction = LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService(eviction_service=eviction)
    return {
        "batch_eviction": batch_eviction, "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "preflight_invalidation_service": preflight_invalidation_service,
        "task_event_service": task_event_service, "task_event_store": task_event_store,
        "cache": cache, "invalidation": invalidation, "reconciliation_service": reconciliation_service,
        "eviction": eviction, "history_store": history_store, "metrics": metrics,
    }


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def _prepared(s, task=None):
    task = task or _task(s["lifecycle_service"])
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    return task, dep, preflight_id, _snapshot(s, task, preflight_id)


def _cache_entry(s, task, preflight_id, snapshot):
    """Store an impact entry directly (bypassing the integrated path's own invalidation pass)."""
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )
    return s["cache"].put(task.task_id, preflight_id, plain.reconcile(task.task_id, snapshot.snapshot_id))


def _untrust(s, snapshot):
    s["trust_service"].validate(snapshot.task_id, snapshot.snapshot_id)  # integrity baseline
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def _statuses(result):
    return {i.preflight_id: i.status for i in result.items}


def _obsolete_and_active(s, task, dep=None):
    """A task with two superseded preflights (entries cached) and one current valid one."""
    old_one, _, old_preflight_one, old_snapshot_one = _prepared(s, task)
    _cache_entry(s, task, old_preflight_one, old_snapshot_one)
    old_preflight_two = _new_preflight(s["preflight_store"], task.task_id)
    old_snapshot_two = _snapshot(s, task, old_preflight_two)
    _cache_entry(s, task, old_preflight_two, old_snapshot_two)
    current = _new_preflight(s["preflight_store"], task.task_id)
    _cache_entry(s, task, current, _snapshot(s, task, current))
    return old_preflight_one, old_preflight_two, current


def test_mixed_active_and_obsolete_entries():
    s = _stack()
    task = _task(s["lifecycle_service"])
    old_one, old_two, current = _obsolete_and_active(s, task)
    active_entry = next(e for e in s["cache"].list_entries(task.task_id) if e.preflight_id == current)

    result = s["batch_eviction"].evict(task.task_id)

    assert _statuses(result) == {old_one: BATCH_EVICTED, old_two: BATCH_EVICTED, current: BATCH_EVICTION_SKIPPED}
    assert (result.total, result.evicted_count, result.skipped_count, result.failed_count) == (3, 2, 1, 0)
    assert next(i for i in result.items if i.preflight_id == current).reasons == (PROTECTED_VALID,)
    assert s["cache"].list_entries(task.task_id) == [active_entry]  # the newest valid entry survived


def test_superseded_versions_are_evicted():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)  # version 2 supersedes the entry's version 1

    plan = s["batch_eviction"].plan(task.task_id)
    result = s["batch_eviction"].evict(task.task_id, plan)

    assert [(c.preflight_id, c.version) for c in plan.plan.eligible] == [(preflight_id, 1)]
    assert _statuses(result) == {preflight_id: BATCH_EVICTED} and result.items[0].version == 1
    assert s["cache"].list_entries(task.task_id) == []


def test_invalidated_entries_are_evicted():
    s = _stack()
    task, dep, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")
    other, other_dep, other_preflight, other_snapshot = _prepared(s)
    _cache_entry(s, other, other_preflight, other_snapshot)
    s["task_event_service"].emit(other_dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "completed"})

    by_preflight = s["batch_eviction"].evict(task.task_id)
    by_dependency = s["batch_eviction"].evict(other.task_id)

    assert "operator judgment" in " ".join(by_preflight.items[0].reasons) and by_preflight.evicted_count == 1
    assert LIFECYCLE_TRANSITIONED in by_dependency.items[0].reasons[0] and by_dependency.evicted_count == 1


def test_retention_boundaries_for_unprovable_entries():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    entry = _cache_entry(s, task, preflight_id, snapshot)
    _untrust(s, snapshot)  # neither obsolete nor valid

    inside = s["batch_eviction"].plan(task.task_id, before=entry.cached_at - timedelta(microseconds=1))
    at_boundary = s["batch_eviction"].plan(task.task_id, before=entry.cached_at)  # inclusive
    default = s["batch_eviction"].plan(task.task_id)  # the existing 30-day window: a fresh entry is kept

    assert inside.plan.eligible == () and inside.plan.protected[0].reason == PROTECTED_WITHIN_RETENTION
    assert at_boundary.plan.eligible[0].reasons == (EXPIRED_UNPROVABLE,)
    assert default.plan.eligible == ()
    kept = s["batch_eviction"].evict(task.task_id, inside)
    assert kept.evicted_count == 0 and s["cache"].list_entries(task.task_id)
    gone = s["batch_eviction"].evict(task.task_id, at_boundary)
    assert gone.evicted_count == 1 and s["cache"].list_entries(task.task_id) == []


def test_active_valid_entry_is_never_evicted_however_old():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    entry = _cache_entry(s, task, preflight_id, snapshot)

    result = s["batch_eviction"].evict(task.task_id, s["batch_eviction"].plan(task.task_id, before=entry.cached_at + timedelta(days=3650)))

    assert _statuses(result) == {preflight_id: BATCH_EVICTION_SKIPPED} and result.evicted_count == 0
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_partial_failure_keeps_the_other_evictions():
    s = _stack()
    task = _task(s["lifecycle_service"])
    old_one, old_two, current = _obsolete_and_active(s, task)
    real = s["cache"].evict

    def flaky(task_id, preflight_id):
        if preflight_id == old_one:
            raise RuntimeError("store offline")
        return real(task_id, preflight_id)

    s["cache"].evict = flaky
    result = s["batch_eviction"].evict(task.task_id)

    assert _statuses(result) == {old_one: BATCH_EVICTION_FAILED, old_two: BATCH_EVICTED, current: BATCH_EVICTION_SKIPPED}
    assert "store offline" in next(i for i in result.items if i.preflight_id == old_one).reasons[0]
    assert (result.evicted_count, result.failed_count) == (1, 1)
    assert {e.preflight_id for e in s["cache"].list_entries(task.task_id)} == {old_one, current}  # the failed one is left in place


def test_empty_plans():
    s = _stack()
    task = _task(s["lifecycle_service"])

    empty_task = s["batch_eviction"].evict(task.task_id)
    empty_ids = s["batch_eviction"].evict(task.task_id, s["batch_eviction"].plan(task.task_id, []))
    only_current, _, current_preflight, current_snapshot = _prepared(s)
    _cache_entry(s, only_current, current_preflight, current_snapshot)
    nothing_obsolete = s["batch_eviction"].evict(only_current.task_id)

    for result in (empty_task, empty_ids):
        assert result.items == () and (result.total, result.evicted_count, result.failed_count) == (0, 0, 0)
    assert nothing_obsolete.evicted_count == 0 and nothing_obsolete.plan.plan.eligible == ()


def test_requested_preflights_narrow_the_batch():
    s = _stack()
    task = _task(s["lifecycle_service"])
    old_one, old_two, current = _obsolete_and_active(s, task)

    plan = s["batch_eviction"].plan(task.task_id, [old_one, "no-such-preflight", old_one])
    result = s["batch_eviction"].evict(task.task_id, plan)

    assert plan.requested_preflight_ids == (old_one, "no-such-preflight") and plan.unmatched_preflight_ids == ("no-such-preflight",)
    assert _statuses(result) == {old_one: BATCH_EVICTED, "no-such-preflight": BATCH_EVICTION_SKIPPED}
    assert {e.preflight_id for e in s["cache"].list_entries(task.task_id)} == {old_two, current}  # not requested: not touched


def test_repeated_eviction_is_idempotent():
    s = _stack()
    task = _task(s["lifecycle_service"])
    old_one, old_two, current = _obsolete_and_active(s, task)
    plan = s["batch_eviction"].plan(task.task_id)

    first = s["batch_eviction"].evict(task.task_id, plan)
    entries, events = s["cache"].list_entries(task.task_id), len(s["history_store"].all())
    replayed = s["batch_eviction"].evict(task.task_id, plan)  # the same plan again
    fresh = s["batch_eviction"].evict(task.task_id)

    assert first.evicted_count == 2
    assert replayed.evicted_count == 0 and all(
        i.status == BATCH_EVICTION_SKIPPED for i in replayed.items
    )
    assert fresh.evicted_count == 0 and fresh.plan.plan.eligible == ()
    assert s["cache"].list_entries(task.task_id) == entries and len(s["history_store"].all()) == events


def test_plan_is_read_only():
    s = _stack()
    task = _task(s["lifecycle_service"])
    _obsolete_and_active(s, task)
    entries, events = s["cache"].list_entries(task.task_id), len(s["task_event_store"].all())

    for _ in range(3):
        s["batch_eviction"].plan(task.task_id)

    assert s["cache"].list_entries(task.task_id) == entries
    assert len(s["task_event_store"].all()) == events and s["history_store"].all() == []


def test_apply_time_recheck_spares_an_entry_recomputed_since_planning():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    newer = _snapshot(s, task, preflight_id)
    plan = s["batch_eviction"].plan(task.task_id)
    assert len(plan.plan.eligible) == 1

    s["reconciliation_service"].reconcile(task.task_id, newer.snapshot_id)  # the normal path replaces it
    result = s["batch_eviction"].evict(task.task_id, plan)

    assert _statuses(result) == {preflight_id: BATCH_EVICTION_SKIPPED} and result.evicted_count == 0
    assert result.items[0].reasons == (REPLACED_SINCE_PLAN,)
    assert s["cache"].get(task.task_id, preflight_id).snapshot_id == newer.snapshot_id


def test_history_and_recovery_state_are_preserved():
    s = _stack()
    task = _task(s["lifecycle_service"])
    old_one, old_two, current = _obsolete_and_active(s, task)
    dep_ids = s["dependency_service"].get_dependencies(task.task_id)

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state,
            s["preflight_store"].history(task.task_id), s["dependency_service"].get_dependencies(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            [s["version_service"].list_versions(task.task_id, p) for p in (old_one, old_two, current)],
            s["preflight_invalidation_service"].get_invalidation(current), s["task_event_store"].all(),
            s["metrics"].summary(task.task_id).invalidations,
        )

    before = state()
    s["batch_eviction"].evict(task.task_id)

    assert state() == before and dep_ids == s["dependency_service"].get_dependencies(task.task_id)
    events = s["history_store"].list_for_task(task.task_id)  # #5's own audit trail: one event per real eviction
    assert sorted(e.payload["preflight_id"] for e in events) == sorted([old_one, old_two])
    assert all(e.event_type == IMPACT_CACHE_EVICTED_EVENT_TYPE for e in events)


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["batch_eviction"].plan(bad)
        with pytest.raises(Error):
            s["batch_eviction"].evict(bad)
    with pytest.raises(Error):
        s["batch_eviction"].plan("task", "not-a-list")
    with pytest.raises(Error):
        s["batch_eviction"].plan("task", ["ok", ""])
    with pytest.raises(Error):
        s["batch_eviction"].plan("task", before="yesterday")
    with pytest.raises(Error):
        s["batch_eviction"].evict("task", plan="not a plan")
    with pytest.raises(Error):
        s["batch_eviction"].evict("task", s["batch_eviction"].plan("other-task"))
