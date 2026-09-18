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
    EXPIRED_UNPROVABLE,
    IMPACT_CACHE_EVICTED_EVENT_TYPE,
    PROTECTED_VALID,
    PROTECTED_WITHIN_RETENTION,
    REPLACED_SINCE_PLAN,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError,
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
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
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


def test_obsolete_snapshot_version_is_evicted():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)  # version 2 supersedes the entry's version 1

    plan = s["eviction"].plan(task.task_id)
    result = s["eviction"].evict(task.task_id, plan)

    assert [c.preflight_id for c in plan.eligible] == [preflight_id]
    assert (plan.eligible[0].snapshot_id, plan.eligible[0].version) == (snapshot.snapshot_id, 1)
    assert "no longer" in plan.eligible[0].reasons[0]
    assert len(result.evicted) == 1
    assert s["cache"].list_entries(task.task_id) == []


def test_entry_of_superseded_preflight_is_evicted():
    s = _stack()
    task, _, old_preflight, snapshot = _prepared(s)
    _cache_entry(s, task, old_preflight, snapshot)
    _new_preflight(s["preflight_store"], task.task_id)  # supersedes the entry's preflight

    plan = s["eviction"].plan(task.task_id)

    assert [c.preflight_id for c in plan.eligible] == [old_preflight]
    assert any("current preflight" in reason for reason in plan.eligible[0].reasons)


def test_entry_of_invalidated_preflight_is_evicted():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    result = s["eviction"].evict(task.task_id)

    assert len(result.evicted) == 1
    assert "operator judgment" in " ".join(result.evicted[0].reasons)
    assert s["cache"].list_entries(task.task_id) == []


def test_entry_invalidated_by_dependency_change_is_evicted():
    s = _stack()
    task, dep, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    s["task_event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "completed"})

    plan = s["eviction"].plan(task.task_id)

    assert [c.preflight_id for c in plan.eligible] == [preflight_id]
    assert LIFECYCLE_TRANSITIONED in plan.eligible[0].reasons[0]


def test_active_valid_entry_is_never_evicted_however_old():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    entry = _cache_entry(s, task, preflight_id, snapshot)
    far_future = entry.cached_at + timedelta(days=3650)

    plan = s["eviction"].plan(task.task_id, before=far_future)
    result = s["eviction"].evict(task.task_id, plan)

    assert plan.eligible == ()
    assert [p.reason for p in plan.protected] == [PROTECTED_VALID]
    assert result.evicted == ()
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_retention_boundary_for_entries_that_are_not_provably_consumable():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    entry = _cache_entry(s, task, preflight_id, snapshot)
    _untrust(s, snapshot)  # neither obsolete nor valid: unprovable

    inside = s["eviction"].plan(task.task_id, before=entry.cached_at - timedelta(microseconds=1))
    at_boundary = s["eviction"].plan(task.task_id, before=entry.cached_at)  # inclusive, like event retention
    outside = s["eviction"].plan(task.task_id, before=entry.cached_at + timedelta(seconds=1))

    assert inside.eligible == () and inside.protected[0].reason == PROTECTED_WITHIN_RETENTION
    assert at_boundary.eligible[0].reasons == (EXPIRED_UNPROVABLE,)
    assert outside.eligible[0].reasons == (EXPIRED_UNPROVABLE,)


def test_default_cutoff_reuses_existing_event_retention_window():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _untrust(s, snapshot)

    plan = s["eviction"].plan(task.task_id)

    assert DEFAULT_RETENTION_WINDOW == timedelta(days=30)
    assert abs((datetime.now(timezone.utc) - DEFAULT_RETENTION_WINDOW) - plan.before) < timedelta(seconds=5)
    assert plan.eligible == () and plan.protected[0].reason == PROTECTED_WITHIN_RETENTION  # a fresh entry is kept

    shorter = LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService(
        cache_service=s["cache"], retention_window=timedelta(seconds=-1)
    )
    assert shorter.plan(task.task_id).eligible[0].reasons == (EXPIRED_UNPROVABLE,)  # configurable window


def test_only_obsolete_entries_are_evicted_among_several():
    s = _stack()
    task, dep, old_preflight, old_snapshot = _prepared(s)
    _cache_entry(s, task, old_preflight, old_snapshot)
    current_preflight = _new_preflight(s["preflight_store"], task.task_id)
    current_snapshot = _snapshot(s, task, current_preflight)
    _cache_entry(s, task, current_preflight, current_snapshot)
    other, _, other_preflight, other_snapshot = _prepared(s)
    _cache_entry(s, other, other_preflight, other_snapshot)

    result = s["eviction"].evict(task.task_id)

    assert [c.preflight_id for c in result.evicted] == [old_preflight]
    assert [p.preflight_id for p in result.plan.protected] == [current_preflight]
    assert [e.preflight_id for e in s["cache"].list_entries(task.task_id)] == [current_preflight]
    assert len(s["cache"].list_entries(other.task_id)) == 1  # other tasks untouched


def test_empty_plan_and_eviction():
    s = _stack()
    task = _task(s["lifecycle_service"])

    plan = s["eviction"].plan(task.task_id)
    result = s["eviction"].evict(task.task_id, plan)

    assert plan.eligible == () and plan.protected == ()
    assert result.evicted == () and result.already_evicted == () and result.newly_protected == ()
    assert s["eviction"].evict(task.task_id).evicted == ()


def test_repeated_eviction_is_idempotent():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)
    plan = s["eviction"].plan(task.task_id)

    first = s["eviction"].evict(task.task_id, plan)
    replayed = s["eviction"].evict(task.task_id, plan)  # same plan again
    fresh = s["eviction"].evict(task.task_id)

    assert len(first.evicted) == 1
    assert replayed.evicted == () and len(replayed.already_evicted) == 1
    assert fresh.evicted == () and fresh.plan.eligible == ()
    assert len(s["history_store"].list_for_task(task.task_id)) == 1  # audited once, for the real eviction


def test_plan_is_read_only():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)
    entries_before = s["cache"].list_entries(task.task_id)
    events_before = len(s["task_event_store"].all())

    for _ in range(3):
        s["eviction"].plan(task.task_id)

    assert s["cache"].list_entries(task.task_id) == entries_before
    assert len(s["task_event_store"].all()) == events_before
    assert s["history_store"].all() == []


def test_apply_time_recheck_spares_entry_recomputed_since_planning():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    newer = _snapshot(s, task, preflight_id)
    plan = s["eviction"].plan(task.task_id)
    assert len(plan.eligible) == 1

    s["reconciliation_service"].reconcile(task.task_id, newer.snapshot_id)  # normal path recomputes and replaces it
    result = s["eviction"].evict(task.task_id, plan)

    assert result.evicted == ()
    assert result.newly_protected[0].reason == REPLACED_SINCE_PLAN
    assert s["cache"].get(task.task_id, preflight_id).snapshot_id == newer.snapshot_id


def test_apply_time_recheck_spares_entry_that_became_valid():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    entry = _cache_entry(s, task, preflight_id, snapshot)
    plan = s["eviction"].plan(task.task_id, before=entry.cached_at)
    assert plan.eligible == ()
    stale_plan = replace(
        plan, eligible=(s["eviction"]._candidate(entry, (EXPIRED_UNPROVABLE,)),), protected=()
    )  # a plan claiming an age-expiry for what is in fact a valid entry

    result = s["eviction"].evict(task.task_id, stale_plan)

    assert result.evicted == () and result.newly_protected[0].reason == PROTECTED_VALID
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_eviction_never_touches_recovery_state_or_audit_evidence():
    s = _stack()
    task, dep, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    s["task_event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={})
    s["invalidation"].reconcile(task.task_id)  # leaves invalidation history behind
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state,
            s["lifecycle_service"].get(dep.task_id).current_state,
            s["preflight_store"].history(task.task_id),
            s["dependency_service"].get_dependencies(task.task_id),
            s["snapshot_service"]._store.list_for_task(task.task_id),
            s["version_service"].list_versions(task.task_id, preflight_id),
            s["preflight_invalidation_service"].get_invalidation(preflight_id),
            s["task_event_store"].all(),
            s["metrics"].summary(task.task_id).invalidations,
        )

    before = state()
    assert len(s["eviction"].evict(task.task_id).evicted) == 1

    assert state() == before  # eviction is not an invalidation either: metrics unchanged


def test_recovery_behaviour_is_unchanged_after_eviction():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    cached = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    newer = _snapshot(s, task, preflight_id)  # obsoletes the cached entry
    s["eviction"].evict(task.task_id)
    assert s["cache"].list_entries(task.task_id) == []

    after = s["reconciliation_service"].reconcile(task.task_id, newer.snapshot_id)
    reference = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    ).reconcile(task.task_id, newer.snapshot_id)

    assert cached.status == after.status == reference.status == UNCHANGED
    assert (after.added, after.removed, after.resolved) == (reference.added, reference.removed, reference.resolved)
    assert s["cache"].get(task.task_id, preflight_id) is not None  # repopulated by the normal path


def test_eviction_history_records_references_and_reasons():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)

    s["eviction"].evict(task.task_id)

    (event,) = s["history_store"].list_for_task(task.task_id)
    assert event.event_type == IMPACT_CACHE_EVICTED_EVENT_TYPE
    assert event.payload["preflight_id"] == preflight_id
    assert event.payload["snapshot_id"] == snapshot.snapshot_id
    assert event.payload["version"] == 1 and event.payload["reasons"]


def test_failing_history_never_blocks_eviction():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)

    class _Broken:
        def emit(self, *args, **kwargs):
            raise RuntimeError("event store offline")

    s["eviction"]._event_service = _Broken()

    assert len(s["eviction"].evict(task.task_id).evicted) == 1
    assert s["cache"].list_entries(task.task_id) == []


def test_without_invalidation_service_still_evicts_obsolete_snapshots():
    s = _stack(with_invalidation=False)
    task, _, preflight_id, snapshot = _prepared(s)
    _cache_entry(s, task, preflight_id, snapshot)
    _snapshot(s, task, preflight_id)

    result = s["eviction"].evict(task.task_id)

    assert len(result.evicted) == 1
    assert "no longer" in result.evicted[0].reasons[0]


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["eviction"].plan(bad)
        with pytest.raises(Error):
            s["eviction"].evict(bad)
    with pytest.raises(Error):
        s["eviction"].plan("task", before="yesterday")
    with pytest.raises(Error):
        s["eviction"].evict("task", plan="not a plan")
    other_plan = s["eviction"].plan("other-task")
    with pytest.raises(Error):
        s["eviction"].evict("task", other_plan)
