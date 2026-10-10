import itertools
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import (
    DEPENDENCY_ADDED,
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    IMPACT_CACHE_INVALIDATED_EVENT_TYPE,
    TRIGGER_DEPENDENCY,
    TRIGGER_PREFLIGHT,
    TRIGGER_RECONCILE,
    TRIGGER_SNAPSHOT,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(lifecycle_service):
    return lifecycle_service.create({"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"})


def _complete(lifecycle_service, task):
    for target in (PLANNED, TASK_READY, RUNNING, COMPLETED):
        lifecycle_service.transition(task.task_id, target)


_preflight_counter = itertools.count()


def _new_preflight(preflight_store, task_id):
    # store.save() is idempotent for identical content, so each preflight must differ
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=ALLOW,
        blocking_reasons=(), warnings=(f"run-{next(_preflight_counter)}",),
        checked_at=NOW.replace(microsecond=next(_preflight_counter)),
    )
    return preflight_store.save(result).preflight_id


def _stack(with_events=True, with_history=True, track_preflights=True):
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    event_store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(event_store)
    event_query_service = LLMAgentTaskEventQueryService(event_store)
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(snapshot_service=snapshot_service)
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, dependency_service=dependency_service,
        preflight_store=preflight_store if track_preflights else None,
        preflight_invalidation_service=preflight_invalidation_service,
        event_query_service=event_query_service if with_events else None,
        event_service=event_service if with_history else None,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, impact_cache_service=cache, impact_cache_invalidation_service=invalidation,
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service,
        "preflight_invalidation_service": preflight_invalidation_service,
        "event_service": event_service, "event_query_service": event_query_service,
        "cache": cache, "invalidation": invalidation, "reconciliation_service": reconciliation_service,
    }


def _cached(s, task, dependency_tasks=()):
    """Snapshot a fresh preflight for task and cache its impact result."""
    for dependency_task in dependency_tasks:
        s["dependency_service"].add_dependency(task.task_id, dependency_task.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert s["cache"].get(task.task_id, preflight_id) == result
    return preflight_id, snapshot


def _history(s, task_id):
    return s["event_query_service"].query(task_id=task_id, event_types=[IMPACT_CACHE_INVALIDATED_EVENT_TYPE])


def test_dependency_change_invalidates_affected_entry():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])

    result = s["invalidation"].invalidate_for_dependency(task.task_id, dep.task_id)

    assert result.trigger == TRIGGER_DEPENDENCY
    assert result.subject_id == dep.task_id
    assert result.invalidated_count == 1
    assert result.affected[0].preflight_id == preflight_id
    assert result.affected[0].invalidated is True
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_unrelated_dependency_leaves_cache_intact():
    s = _stack()
    task, dep, other = (_task(s["lifecycle_service"]) for _ in range(3))
    preflight_id, _ = _cached(s, task, [dep])

    result = s["invalidation"].invalidate_for_dependency(task.task_id, other.task_id)

    assert result.affected == ()
    assert result.invalidated_count == 0
    assert result.retained_preflight_ids == (preflight_id,)
    assert s["cache"].get(task.task_id, preflight_id) is not None
    assert _history(s, task.task_id) == []


def test_newly_reachable_dependency_invalidates_only_with_dependency_service():
    s = _stack()
    task, dep, added = (_task(s["lifecycle_service"]) for _ in range(3))
    preflight_id, _ = _cached(s, task, [dep])
    s["dependency_service"].add_dependency(task.task_id, added.task_id)  # not in the entry's evidence

    blind = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=s["cache"], snapshot_service=s["snapshot_service"]
    )
    assert blind.invalidate_for_dependency(task.task_id, added.task_id).invalidated_count == 0

    aware = s["invalidation"].invalidate_for_dependency(task.task_id, added.task_id)
    assert aware.invalidated_count == 1
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_unverifiable_evidence_fails_closed():
    s = _stack()
    task, dep, other = (_task(s["lifecycle_service"]) for _ in range(3))
    preflight_id, snapshot = _cached(s, task, [dep])
    del s["snapshot_service"]._store._by_id[snapshot.snapshot_id]  # evidence can no longer be loaded

    result = s["invalidation"].invalidate_for_dependency(task.task_id, other.task_id)

    assert result.invalidated_count == 1
    assert "cannot be verified" in result.affected[0].reasons[0]


def test_multiple_entries_only_affected_ones_removed():
    s = _stack(track_preflights=False)
    task, dep, other = (_task(s["lifecycle_service"]) for _ in range(3))
    first_preflight, _ = _cached(s, task, [dep])
    second_preflight, _ = _cached(s, task)  # graph still contains dep, so this entry also depends on it
    # third entry, whose evidence is limited to `other`, cached against a different task
    other_task = _task(s["lifecycle_service"])
    unrelated_preflight, _ = _cached(s, other_task, [other])

    result = s["invalidation"].invalidate_for_dependency(task.task_id, dep.task_id)

    assert {outcome.preflight_id for outcome in result.affected} == {first_preflight, second_preflight}
    assert result.invalidated_count == 2
    assert s["cache"].get(task.task_id, first_preflight) is None
    assert s["cache"].get(task.task_id, second_preflight) is None
    assert s["cache"].get(other_task.task_id, unrelated_preflight) is not None


def test_preflight_invalidation_removes_only_that_entry():
    s = _stack(track_preflights=False)
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    first_preflight, _ = _cached(s, task, [dep])
    second_preflight, _ = _cached(s, task)

    result = s["invalidation"].invalidate_for_preflight(task.task_id, first_preflight)

    assert result.trigger == TRIGGER_PREFLIGHT
    assert [outcome.preflight_id for outcome in result.affected] == [first_preflight]
    assert result.retained_preflight_ids == (second_preflight,)
    assert s["cache"].get(task.task_id, second_preflight) is not None


def test_reconcile_detects_guardrail_preflight_invalidation():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    result = s["invalidation"].reconcile(task.task_id)

    assert result.trigger == TRIGGER_RECONCILE
    assert result.invalidated_count == 1
    assert "operator judgment" in " ".join(result.affected[0].reasons)
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_caching_a_newer_preflight_evicts_the_superseded_entry():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    first_preflight, _ = _cached(s, task, [dep])

    second_preflight, _ = _cached(s, task)  # the integrated path reconciles before consulting the cache

    assert s["cache"].get(task.task_id, first_preflight) is None
    assert [entry.preflight_id for entry in s["cache"].list_entries(task.task_id)] == [second_preflight]


def test_reconcile_detects_superseded_preflight():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    _new_preflight(s["preflight_store"], task.task_id)  # a newer preflight replaces it

    result = s["invalidation"].reconcile(task.task_id)

    assert result.invalidated_count == 1
    assert any("current preflight" in reason for reason in result.affected[0].reasons)


def test_snapshot_replacement_invalidates_old_entry():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, old_snapshot = _cached(s, task, [dep])
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    result = s["invalidation"].invalidate_for_snapshot(task.task_id, new_snapshot.snapshot_id)

    assert result.trigger == TRIGGER_SNAPSHOT
    assert result.invalidated_count == 1
    assert result.affected[0].snapshot_id == old_snapshot.snapshot_id
    assert "replaced" in result.affected[0].reasons[0]


def test_invalidate_for_snapshot_by_bound_snapshot_id():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, snapshot = _cached(s, task, [dep])

    result = s["invalidation"].invalidate_for_snapshot(task.task_id, snapshot.snapshot_id)

    assert result.invalidated_count == 1
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_reconcile_detects_replaced_snapshot():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    s["snapshot_service"].create(task.task_id, preflight_id)

    result = s["invalidation"].reconcile(task.task_id)

    assert result.invalidated_count == 1
    assert "no longer" in result.affected[0].reasons[0]


def test_reconcile_event_signal_on_evidence_dependency():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])

    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "completed"})
    result = s["invalidation"].reconcile(task.task_id)

    assert result.invalidated_count == 1
    assert LIFECYCLE_TRANSITIONED in result.affected[0].reasons[0]
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_reconcile_event_signal_on_task_edge_change():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])

    s["event_service"].emit(task.task_id, DEPENDENCY_ADDED, payload={"dependency_task_id": "new-dep"})

    assert s["invalidation"].reconcile(task.task_id).invalidated_count == 1


def test_events_before_computation_do_not_invalidate():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "running"})
    preflight_id, _ = _cached(s, task, [dep])  # computed AFTER the event, so already reflects it

    result = s["invalidation"].reconcile(task.task_id)

    assert result.invalidated_count == 0
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_unrelated_changes_leave_cache_intact():
    s = _stack()
    task, dep, stranger = (_task(s["lifecycle_service"]) for _ in range(3))
    preflight_id, _ = _cached(s, task, [dep])

    s["event_service"].emit(stranger.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "completed"})
    s["event_service"].emit(stranger.task_id, DEPENDENCY_ADDED, payload={})
    s["event_service"].emit(task.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "running"})  # own state
    result = s["invalidation"].reconcile(task.task_id)

    assert result.affected == ()
    assert result.retained_preflight_ids == (preflight_id,)
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_reconcile_without_event_service_uses_state_signals_only():
    s = _stack(with_events=False)
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={})

    assert s["invalidation"].reconcile(task.task_id).invalidated_count == 0
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_repeated_invalidation_is_idempotent():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={})

    first = s["invalidation"].reconcile(task.task_id)
    second = s["invalidation"].reconcile(task.task_id)
    third = s["invalidation"].invalidate_for_preflight(task.task_id, preflight_id)

    assert first.invalidated_count == 1
    assert second.affected == () and second.invalidated_count == 0
    assert third.affected == () and third.invalidated_count == 0
    assert len(_history(s, task.task_id)) == 1  # history appended once, only for the real removal


def test_reconcile_never_removes_entry_recomputed_after_the_change():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, snapshot = _cached(s, task, [dep])
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={})
    s["invalidation"].reconcile(task.task_id)

    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)  # recomputed after the event

    assert s["invalidation"].reconcile(task.task_id).affected == ()
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_history_metadata_preserved_on_event_stream():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, snapshot = _cached(s, task, [dep])

    s["invalidation"].invalidate_for_dependency(task.task_id, dep.task_id)

    (event,) = _history(s, task.task_id)
    assert event.payload["preflight_id"] == preflight_id
    assert event.payload["snapshot_id"] == snapshot.snapshot_id
    assert event.payload["trigger"] == TRIGGER_DEPENDENCY
    assert event.payload["reasons"]


def test_failing_history_never_blocks_invalidation():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])

    class _Broken:
        def emit(self, *args, **kwargs):
            raise RuntimeError("event store offline")

    s["invalidation"]._event_service = _Broken()

    assert s["invalidation"].invalidate_for_preflight(task.task_id, preflight_id).invalidated_count == 1
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_integrated_reconcile_no_longer_serves_stale_impact():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, snapshot = _cached(s, task, [dep])

    _complete(s["lifecycle_service"], dep)
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})
    fresh = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert fresh.status == CHANGED  # #1 alone would have served the stale UNCHANGED entry
    assert fresh.resolved == (dep.task_id,)
    assert s["cache"].get(task.task_id, preflight_id) == fresh


def test_integrated_reconcile_uses_cache_when_nothing_changed():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    _, snapshot = _cached(s, task, [dep])
    calls = []
    original = s["snapshot_service"].diff
    s["snapshot_service"].diff = lambda *a, **k: (calls.append(1), original(*a, **k))[1]

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert calls == []


def test_invalidation_failure_falls_back_to_fresh_analysis():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    _, snapshot = _cached(s, task, [dep])
    _complete(s["lifecycle_service"], dep)

    class _Broken:
        def reconcile(self, task_id):
            raise RuntimeError("cannot determine staleness")

    s["reconciliation_service"]._impact_cache_invalidation_service = _Broken()
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == CHANGED  # the cache was not consulted; the fresh diff saw the change


def test_trust_invalidation_also_removes_cached_impact():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(snapshot_service=snapshot_service)
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service
    )
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(snapshot_service=snapshot_service)
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service
    )
    trust_invalidation = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService(
        snapshot_service=snapshot_service,
        trust_change_service=LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(trust_service=trust_service),
        preflight_store=preflight_store,
        preflight_invalidation_service=LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store),
        impact_cache_invalidation_service=invalidation,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, impact_cache_service=cache
    )
    task = _task(lifecycle_service)
    preflight_id = _new_preflight(preflight_store, task.task_id)
    snapshot = snapshot_service.create(task.task_id, preflight_id)
    trust_service.validate(task.task_id, snapshot.snapshot_id)  # integrity baseline
    reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)
    assert cache.get(task.task_id, preflight_id) is not None

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    snapshot_service._store._by_id[snapshot.snapshot_id] = tampered
    result = trust_invalidation.invalidate(task.task_id, snapshot.snapshot_id)

    assert result.warranted is True
    assert cache.list_entries(task.task_id) == []


def test_invalidation_never_mutates_recovery_state():
    s = _stack()
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    preflight_id, _ = _cached(s, task, [dep])
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={})
    before = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["preflight_store"].history(task.task_id),
        s["snapshot_service"]._store.list_for_task(task.task_id),
        s["dependency_service"].get_dependencies(task.task_id),
        s["preflight_invalidation_service"].get_invalidation(preflight_id),
    )

    s["invalidation"].reconcile(task.task_id)
    s["invalidation"].invalidate_for_dependency(task.task_id, dep.task_id)

    after = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["preflight_store"].history(task.task_id),
        s["snapshot_service"]._store.list_for_task(task.task_id),
        s["dependency_service"].get_dependencies(task.task_id),
        s["preflight_invalidation_service"].get_invalidation(preflight_id),
    )
    assert after == before


def test_empty_cache_is_a_clean_noop():
    s = _stack()
    task = _task(s["lifecycle_service"])

    result = s["invalidation"].reconcile(task.task_id)

    assert result.affected == () and result.retained_preflight_ids == () and result.invalidated_count == 0


def test_validation():
    s = _stack()
    for bad in ("", None, 5):
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError):
            s["invalidation"].reconcile(bad)
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError):
            s["invalidation"].invalidate_for_dependency("task", bad)
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError):
            s["invalidation"].invalidate_for_preflight(bad, "preflight")
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationError):
            s["invalidation"].invalidate_for_snapshot("task", bad)
