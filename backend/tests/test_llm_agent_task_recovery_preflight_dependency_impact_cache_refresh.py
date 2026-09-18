import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventService
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    CURRENT,
    IMPACT_CACHE_REFRESHED_EVENT_TYPE,
    NEWER_ENTRY,
    NOT_REFRESHED,
    NOT_TRUSTED,
    REFRESHED,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService,
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


def _complete(lifecycle_service, task):
    for target in (PLANNED, TASK_READY, RUNNING, COMPLETED):
        lifecycle_service.transition(task.task_id, target)


def _new_preflight(preflight_store, task_id):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=ALLOW, blocking_reasons=(),
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
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service, trust_service=trust_service
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service, impact_cache_service=cache
    )
    analyses = []
    original = reconciliation_service.reconcile
    reconciliation_service.reconcile = lambda *a, **k: (analyses.append(k.get("use_cache", True)), original(*a, **k))[1]
    consistency = LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService(
        cache_service=cache, snapshot_service=snapshot_service, reconciliation_service=reconciliation_service,
        preflight_store=preflight_store,
    )
    history_store = InMemoryAgentTaskEventStore()
    refresh = LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService(
        cache_service=cache, consistency_service=consistency, reconciliation_service=reconciliation_service,
        event_service=LLMAgentTaskEventService(history_store),
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "cache": cache, "reconciliation_service": reconciliation_service,
        "consistency": consistency, "refresh": refresh, "history_store": history_store, "analyses": analyses,
    }


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def _cached(s, task=None):
    dep = None
    if task is None:  # extra preflights for the same task must not change its dependency graph
        task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
        s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    snapshot = _snapshot(s, task, preflight_id)
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )
    s["cache"].put(task.task_id, preflight_id, plain.reconcile(task.task_id, snapshot.snapshot_id))
    s["analyses"].clear()
    return task, dep, preflight_id, snapshot


def _entry(s, task, preflight_id):
    return next(e for e in s["cache"].list_entries(task.task_id) if e.preflight_id == preflight_id)


def _overwrite(s, task, preflight_id, **changes):
    s["cache"]._store._entries[(task.task_id, preflight_id)] = replace(_entry(s, task, preflight_id), **changes)


def _untrust(s, snapshot):
    s["trust_service"].validate(snapshot.task_id, snapshot.snapshot_id)  # integrity baseline
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def test_current_cache_is_a_noop():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    entry = _entry(s, task, preflight_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == CURRENT and result.result is None
    assert (result.snapshot_id, result.version) == (snapshot.snapshot_id, 1)
    assert s["analyses"] == []  # no analysis ran
    assert _entry(s, task, preflight_id) == entry


def test_stale_entry_is_refreshed_from_the_latest_snapshot():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    newer = _snapshot(s, task, preflight_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == REFRESHED and result.categories == ("stale",)
    assert (result.snapshot_id, result.version) == (newer.snapshot_id, 2)
    assert _entry(s, task, preflight_id).snapshot_id == newer.snapshot_id
    assert s["cache"].get(task.task_id, preflight_id) == result.result
    assert s["analyses"] == [False]  # exactly one fresh analysis, bypassing the cache


def test_diverged_entry_is_refreshed():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _complete(s["lifecycle_service"], dep)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == REFRESHED and result.categories == ("diverged",)
    assert _entry(s, task, preflight_id).result.status == CHANGED
    assert _entry(s, task, preflight_id).result.resolved == (dep.task_id,)


def test_inconsistent_entry_is_refreshed_even_when_its_timestamp_is_in_the_future():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    good = _entry(s, task, preflight_id)
    corrupt = replace(good.result, status=CHANGED, reconciled_at=good.result.reconciled_at + timedelta(days=1))
    _overwrite(s, task, preflight_id, result=corrupt)  # contradictory AND future-dated

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == REFRESHED and "corrupted" in result.categories
    assert _entry(s, task, preflight_id).result.status == UNCHANGED


def test_missing_entry_is_created():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    s["cache"].invalidate(task.task_id, preflight_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == REFRESHED and result.categories == ("missing",)
    assert s["cache"].get(task.task_id, preflight_id) is not None


def test_no_snapshot_means_nothing_to_refresh_from():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == NOT_REFRESHED and s["analyses"] == []
    assert s["cache"].list_entries(task.task_id) == []


def test_entry_bound_to_a_newer_version_is_protected():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _overwrite(s, task, preflight_id, version=5)  # cache is ahead of the resolved latest (v1)
    entry = _entry(s, task, preflight_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == NEWER_ENTRY and s["analyses"] == []
    assert _entry(s, task, preflight_id) == entry


def test_newer_entry_written_during_refresh_is_never_overwritten():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    newer = _snapshot(s, task, preflight_id)
    real = s["reconciliation_service"].reconcile

    def racing(task_id, snapshot_id, **kwargs):
        result = real(task_id, snapshot_id, **kwargs)
        s["cache"].invalidate(task_id, preflight_id)
        s["cache"].put(
            task_id, preflight_id,
            replace(result, added=("raced",), status=CHANGED, reconciled_at=result.reconciled_at + timedelta(seconds=5)),
        )
        return result

    s["refresh"]._reconciliation_service = type("R", (), {"reconcile": staticmethod(racing)})()
    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == NEWER_ENTRY
    assert _entry(s, task, preflight_id).result.added == ("raced",)
    assert _entry(s, task, preflight_id).snapshot_id == newer.snapshot_id


def test_untrusted_snapshot_leaves_the_cache_non_consumable_and_fabricates_nothing():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    _untrust(s, snapshot)
    entry = _entry(s, task, preflight_id)

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == NOT_TRUSTED and result.result is None
    assert s["analyses"] == []
    assert _entry(s, task, preflight_id) == entry  # untouched
    assert s["cache"].get(task.task_id, preflight_id) is None  # and still not consumable


def test_untrusted_missing_entry_is_not_fabricated():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    s["cache"].invalidate(task.task_id, preflight_id)
    _untrust(s, snapshot)

    assert s["refresh"].refresh(task.task_id, preflight_id).status == NOT_TRUSTED
    assert s["cache"].list_entries(task.task_id) == []


def test_analysis_failure_keeps_the_existing_entry():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    newer = _snapshot(s, task, preflight_id)
    entry = _entry(s, task, preflight_id)
    s["refresh"]._reconciliation_service = type(
        "R", (), {"reconcile": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("resolver down"))}
    )()

    result = s["refresh"].refresh(task.task_id, preflight_id)

    assert result.status == NOT_REFRESHED and "resolver down" in result.reasons[0]
    assert _entry(s, task, preflight_id) == entry and newer  # a failed recompute loses nothing


def test_refresh_stale_handles_multiple_stale_entries_and_leaves_consistent_ones():
    s = _stack()
    task, _, first, _ = _cached(s)
    _, _, second, _ = _cached(s, task)
    _, _, third, _ = _cached(s, task)
    _snapshot(s, task, first)   # stale
    _snapshot(s, task, third)   # stale
    consistent_entry = _entry(s, task, second)

    summary = s["refresh"].refresh_stale(task.task_id)

    assert summary.refreshed_count == 2 and summary.consistent_count == 1
    assert {r.preflight_id for r in summary.results} == {first, third}
    assert all(r.status == REFRESHED for r in summary.results)
    assert _entry(s, task, second) == consistent_entry
    assert s["refresh"].refresh_stale(task.task_id).results == ()  # nothing left stale


def test_refresh_stale_reports_mixed_outcomes():
    s = _stack()
    task, _, first, _ = _cached(s)
    _, _, second, second_snapshot = _cached(s, task)
    _snapshot(s, task, first)
    _untrust(s, second_snapshot)

    summary = s["refresh"].refresh_stale(task.task_id)

    assert (summary.refreshed_count, summary.not_trusted_count) == (1, 1)
    assert {r.preflight_id: r.status for r in summary.results} == {first: REFRESHED, second: NOT_TRUSTED}


def test_repeated_refresh_is_idempotent():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)

    first = s["refresh"].refresh(task.task_id, preflight_id)
    entry = _entry(s, task, preflight_id)
    analyses = len(s["analyses"])
    second = s["refresh"].refresh(task.task_id, preflight_id)
    stale_run = s["refresh"].refresh_stale(task.task_id)

    assert (first.status, second.status) == (REFRESHED, CURRENT)
    assert stale_run.refreshed_count == 0
    assert _entry(s, task, preflight_id) == entry and len(s["analyses"]) == analyses
    assert len(s["history_store"].list_for_task(task.task_id)) == 1  # only the real refresh is recorded


def test_refresh_history_records_before_and_after_references():
    s = _stack()
    task, _, preflight_id, old = _cached(s)
    new = _snapshot(s, task, preflight_id)

    s["refresh"].refresh(task.task_id, preflight_id)

    (event,) = s["history_store"].list_for_task(task.task_id)
    assert event.event_type == IMPACT_CACHE_REFRESHED_EVENT_TYPE
    assert (event.payload["previous_snapshot_id"], event.payload["previous_version"]) == (old.snapshot_id, 1)
    assert (event.payload["snapshot_id"], event.payload["version"]) == (new.snapshot_id, 2)


def test_failing_history_never_blocks_refresh():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)

    class _Broken:
        def emit(self, *a, **k):
            raise RuntimeError("event store offline")

    s["refresh"]._event_service = _Broken()

    assert s["refresh"].refresh(task.task_id, preflight_id).status == REFRESHED


def test_consumption_path_refreshes_an_inconsistent_entry_with_a_single_analysis():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    consistency = s["consistency"]
    s["reconciliation_service"]._impact_cache_consistency_service = consistency
    s["reconciliation_service"]._impact_cache_refresh_service = s["refresh"]
    _overwrite(s, task, preflight_id, result=replace(_entry(s, task, preflight_id).result, status=CHANGED))  # contradiction

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert s["analyses"].count(False) == 1  # the refresh's one fresh analysis; reconcile did not repeat it
    assert _entry(s, task, preflight_id).result.status == UNCHANGED  # the cache itself is repaired
    assert consistency.check(task.task_id).is_consistent is True


def test_consumption_path_falls_back_when_refresh_fails():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    s["reconciliation_service"]._impact_cache_consistency_service = s["consistency"]

    class _Broken:
        def refresh(self, *a):
            raise RuntimeError("refresh unavailable")

    s["reconciliation_service"]._impact_cache_refresh_service = _Broken()
    _overwrite(s, task, preflight_id, result=replace(_entry(s, task, preflight_id).result, status=CHANGED))

    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED


def test_refresh_never_touches_recovery_state():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state, s["lifecycle_service"].get(dep.task_id).current_state,
            s["preflight_store"].history(task.task_id), s["dependency_service"].get_dependencies(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            s["version_service"].list_versions(task.task_id, preflight_id),
        )

    before = state()
    s["refresh"].refresh(task.task_id, preflight_id)
    s["refresh"].refresh_stale(task.task_id)

    assert state() == before


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["refresh"].refresh(bad, "preflight")
        with pytest.raises(Error):
            s["refresh"].refresh("task", bad)
        with pytest.raises(Error):
            s["refresh"].refresh_stale(bad)
