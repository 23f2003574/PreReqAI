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
    BATCH_REFRESH_FAILED,
    BATCH_REFRESH_REFRESHED,
    BATCH_REFRESH_SKIPPED,
    CANDIDATE_CURRENT,
    CANDIDATE_INCONSISTENT,
    CANDIDATE_MISSING,
    CANDIDATE_OBSOLETE,
    CANDIDATE_STALE,
    CANDIDATE_UNAVAILABLE,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError,
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
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "preflight_invalidation_service": preflight_invalidation_service,
        "cache": cache, "refresh": refresh, "warming": warming, "batch": batch, "batch_refresh": batch_refresh,
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
    return {i.preflight_id: i.status for i in result.items}


def _approve_all(s):
    """Only a task's latest preflight is eligible in real wiring; approve every one so a batch holds several."""
    s["warming"].eligibility = lambda task_id, preflight_id: ((), None, None)


def test_mixed_current_stale_and_missing_entries():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    stale, _ = _add_preflight(s, task)
    missing, _ = _add_preflight(s, task, cached=False)
    _snapshot(s, task, stale)
    _approve_all(s)
    current_entry = _entry(s, task, current)

    result = s["batch_refresh"].refresh(task.task_id, [current, stale, missing])

    assert _statuses(result) == {current: BATCH_REFRESH_SKIPPED, stale: BATCH_REFRESH_REFRESHED, missing: BATCH_REFRESH_REFRESHED}
    assert {i.preflight_id: i.classification for i in result.items} == {
        current: CANDIDATE_CURRENT, stale: CANDIDATE_STALE, missing: CANDIDATE_MISSING
    }
    assert (result.total, result.refreshed_count, result.skipped_count, result.failed_count) == (3, 2, 1, 0)
    assert _entry(s, task, current) == current_entry  # already-current entries stay untouched
    assert _entry(s, task, stale).version == 2 and _entry(s, task, missing) is not None
    assert sorted(s["analyses"]) == sorted([_entry(s, task, stale).snapshot_id, _entry(s, task, missing).snapshot_id])


def test_inconsistent_entry_is_a_candidate_and_refreshed():
    s = _stack()
    task, dep = _new_task(s)
    current, _ = _add_preflight(s, task)
    _complete(s["lifecycle_service"], dep)  # the live graph moved on: the entry diverged

    plan = s["batch"].plan(task.task_id)
    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert plan.candidates[0].classification == CANDIDATE_INCONSISTENT and plan.candidates[0].refreshable
    assert _statuses(result) == {current: BATCH_REFRESH_REFRESHED}
    assert _entry(s, task, current).result.status == CHANGED


def test_invalid_snapshot_is_skipped_and_nothing_is_stored():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task)
    _untrust(s, snapshot)
    entry = _entry(s, task, current)

    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert _statuses(result) == {current: BATCH_REFRESH_SKIPPED}
    assert result.items[0].classification == CANDIDATE_UNAVAILABLE and "not trusted" in result.items[0].reasons[0]
    assert s["analyses"] == [] and _entry(s, task, current) == entry
    assert s["cache"].get(task.task_id, current) is None  # still non-consumable


def test_untrusted_snapshot_without_an_entry_is_never_fabricated():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task, cached=False)
    _untrust(s, snapshot)

    assert s["batch_refresh"].refresh_stale(task.task_id).skipped_count == 1
    assert s["cache"].list_entries(task.task_id) == []


def test_obsolete_entries_are_neither_rebuilt_nor_removed():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, old)  # even a stale-looking entry of a superseded preflight must not be rebuilt
    old_entry = _entry(s, task, old)

    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert _statuses(result) == {current: BATCH_REFRESH_SKIPPED, old: BATCH_REFRESH_SKIPPED}
    assert next(i for i in result.items if i.preflight_id == old).classification == CANDIDATE_OBSOLETE
    assert _entry(s, task, old) == old_entry and s["analyses"] == []  # unlike #9's reconcile(), nothing removed


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
    result = s["batch_refresh"].refresh(task.task_id, [first, second, third])

    assert [(i.preflight_id, i.status) for i in result.items] == [
        (first, BATCH_REFRESH_REFRESHED), (second, BATCH_REFRESH_FAILED), (third, BATCH_REFRESH_REFRESHED)
    ]
    assert "resolver down" in result.items[1].reasons[0]
    assert (result.refreshed_count, result.failed_count) == (2, 1)
    assert _entry(s, task, first).version == 2 and _entry(s, task, third).version == 2
    assert _entry(s, task, second).version == 1  # left exactly as it was


def test_unsuccessful_refresh_is_reported_as_failed():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    entry = _entry(s, task, current)
    s["refresh"]._reconciliation_service = type(
        "R", (), {"reconcile": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("resolver down"))}
    )()

    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert result.items[0].status == BATCH_REFRESH_FAILED and result.items[0].refresh_status == "not_refreshed"
    assert _entry(s, task, current) == entry


def test_newer_cache_entry_is_never_overwritten():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["cache"]._store._entries[(task.task_id, current)] = replace(_entry(s, task, current), version=5)  # cache is ahead
    entry = _entry(s, task, current)

    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert _statuses(result) == {current: BATCH_REFRESH_SKIPPED} and result.items[0].refresh_status == "newer_entry"
    assert s["analyses"] == [] and _entry(s, task, current) == entry


def test_newer_entry_written_during_refresh_is_never_overwritten():
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
    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert _statuses(result) == {current: BATCH_REFRESH_SKIPPED}
    assert _entry(s, task, current).result.added == ("raced",)


def test_empty_candidate_sets():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)

    explicit = s["batch_refresh"].refresh(task.task_id, [])
    unknown = s["batch_refresh"].refresh_stale("task-without-preflights")
    all_current = s["batch_refresh"].refresh_stale(task.task_id)

    for result in (explicit, unknown):
        assert result.items == () and (result.total, result.refreshed_count, result.failed_count) == (0, 0, 0)
    assert (all_current.refreshed_count, all_current.skipped_count) == (0, 1) and s["analyses"] == []


def test_invalidated_preflights_are_excluded_from_refresh_stale():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    result = s["batch_refresh"].refresh_stale(task.task_id)

    assert result.excluded_preflight_ids == (current,) and result.items == ()


def test_repeated_refresh_is_idempotent():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    first = s["batch_refresh"].refresh_stale(task.task_id)
    entries = s["cache"].list_entries(task.task_id)
    analyses, events = len(s["analyses"]), len(s["history_store"].all())
    second = s["batch_refresh"].refresh_stale(task.task_id)
    third = s["batch_refresh"].refresh(task.task_id, [current])

    assert first.refreshed_count == 1
    for repeat in (second, third):
        assert repeat.refreshed_count == 0 and _statuses(repeat) == {current: BATCH_REFRESH_SKIPPED}
    assert s["cache"].list_entries(task.task_id) == entries
    assert len(s["analyses"]) == analyses and len(s["history_store"].all()) == events


def test_plan_is_read_only_and_matches_what_refresh_does():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    entries, events = s["cache"].list_entries(task.task_id), len(s["history_store"].all())

    plan = s["batch"].plan(task.task_id)
    s["batch"].plan(task.task_id)

    assert [(c.preflight_id, c.classification, c.refreshable) for c in plan.candidates] == [(current, CANDIDATE_STALE, True)]
    assert s["cache"].list_entries(task.task_id) == entries and len(s["history_store"].all()) == events and s["analyses"] == []
    assert _statuses(s["batch_refresh"].refresh_stale(task.task_id)) == {current: BATCH_REFRESH_REFRESHED}


def test_history_and_recovery_state_are_preserved():
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
            s["preflight_invalidation_service"].get_invalidation(current), s["invalidation_history"].all(),
        )

    before = state()
    s["batch_refresh"].refresh_stale(task.task_id)

    assert state() == before  # snapshots, versions, invalidation history: exactly as they were
    (event,) = s["history_store"].list_for_task(task.task_id)  # the refresh's own history, appended once
    assert event.payload["preflight_id"] == current and event.payload["version"] == 2


def test_explicit_ids_are_processed_in_order_without_duplicates():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task, cached=False)

    result = s["batch_refresh"].refresh(task.task_id, [old, "no-such-preflight", current, old])

    assert [i.preflight_id for i in result.items] == [old, "no-such-preflight", current]
    assert _statuses(result) == {old: BATCH_REFRESH_SKIPPED, "no-such-preflight": BATCH_REFRESH_SKIPPED, current: BATCH_REFRESH_REFRESHED}


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["batch_refresh"].refresh(bad)
        with pytest.raises(Error):
            s["batch_refresh"].refresh_stale(bad)
    with pytest.raises(Error):
        s["batch_refresh"].refresh("task", "not-a-list")
    with pytest.raises(Error):
        s["batch_refresh"].refresh("task", ["ok", ""])
