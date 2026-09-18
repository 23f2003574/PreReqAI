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
    PRECOMPUTE_FAILED,
    PRECOMPUTE_REFRESHED,
    PRECOMPUTE_SKIPPED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeService,
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
    precompute = LLMAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeService(
        warming_service=warming, refresh_service=refresh
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "preflight_invalidation_service": preflight_invalidation_service,
        "cache": cache, "refresh": refresh, "warming": warming, "precompute": precompute,
        "history_store": history_store, "analyses": analyses,
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


def test_selective_precompute_refreshes_only_the_current_relevant_preflight():
    s = _stack()
    task, _ = _new_task(s)
    old, old_snapshot = _add_preflight(s, task)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)  # the current preflight's entry is now stale
    old_entry = _entry(s, task, old)

    result = s["precompute"].precompute_active(task.task_id)

    assert _statuses(result) == {current: PRECOMPUTE_REFRESHED, old: PRECOMPUTE_SKIPPED}
    assert [o.preflight_id for o in result.outcomes] == [current, old]  # newest first
    assert "current preflight" in next(o for o in result.outcomes if o.preflight_id == old).reasons[0]
    assert (result.refreshed_count, result.skipped_count, result.failed_count) == (1, 1, 0)
    assert _entry(s, task, old) == old_entry  # the superseded entry was not touched or analysed
    assert s["analyses"] == [_entry(s, task, current).snapshot_id]


def test_invalidated_preflights_are_excluded_from_an_active_run():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task, cached=False)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    result = s["precompute"].precompute_active(task.task_id)

    assert result.excluded_preflight_ids == (current,)
    assert [o.preflight_id for o in result.outcomes] == [old] and result.outcomes[0].status == PRECOMPUTE_SKIPPED
    assert s["analyses"] == []


def test_already_current_entries_are_skipped_without_analysis():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task)
    entry = _entry(s, task, current)

    result = s["precompute"].precompute_active(task.task_id)

    outcome = result.outcomes[0]
    assert outcome.status == PRECOMPUTE_SKIPPED and outcome.refresh_status == "current"
    assert (outcome.snapshot_id, outcome.version) == (snapshot.snapshot_id, 1)
    assert s["analyses"] == [] and _entry(s, task, current) == entry


def test_stale_and_missing_entries_are_refreshed():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    newer = _snapshot(s, task, current)
    stale = s["precompute"].precompute_active(task.task_id)
    assert stale.outcomes[0].status == PRECOMPUTE_REFRESHED and stale.outcomes[0].snapshot_id == newer.snapshot_id
    assert _entry(s, task, current).snapshot_id == newer.snapshot_id

    other, _ = _new_task(s)
    missing_preflight, _ = _add_preflight(s, other, cached=False)  # no entry at all
    missing = s["precompute"].precompute_active(other.task_id)
    assert _statuses(missing) == {missing_preflight: PRECOMPUTE_REFRESHED}
    assert s["cache"].get(other.task_id, missing_preflight) is not None


def test_diverged_dependency_state_is_refreshed():
    s = _stack()
    task, dep = _new_task(s)
    current, _ = _add_preflight(s, task)
    _complete(s["lifecycle_service"], dep)

    result = s["precompute"].precompute_active(task.task_id)

    assert result.outcomes[0].status == PRECOMPUTE_REFRESHED
    assert _entry(s, task, current).result.status == CHANGED


def test_untrusted_snapshot_is_skipped_and_never_analysed():
    s = _stack()
    task, _ = _new_task(s)
    current, snapshot = _add_preflight(s, task)
    _untrust(s, snapshot)
    entry = _entry(s, task, current)

    result = s["precompute"].precompute_active(task.task_id)

    assert result.outcomes[0].status == PRECOMPUTE_SKIPPED
    assert "not trusted" in result.outcomes[0].reasons[0]
    assert s["analyses"] == [] and _entry(s, task, current) == entry
    assert s["cache"].get(task.task_id, current) is None  # still non-consumable


def test_denied_preflight_is_skipped():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task, cached=False, decision=DENY)

    result = s["precompute"].precompute_active(task.task_id)

    assert result.outcomes[0].status == PRECOMPUTE_SKIPPED and "deny" in result.outcomes[0].reasons[0]
    assert s["analyses"] == [] and s["cache"].list_entries(task.task_id) == []


def test_one_failure_never_discards_the_other_results():
    s = _stack()
    task, _ = _new_task(s)
    first, _ = _add_preflight(s, task)
    second, _ = _add_preflight(s, task)
    third, _ = _add_preflight(s, task)
    for preflight_id in (first, second, third):
        _snapshot(s, task, preflight_id)  # all three entries are stale
    # approve all three so several preflights are processed in one run (only the latest is eligible in real wiring)
    s["warming"].eligibility = lambda task_id, preflight_id: ((), None, None)
    real = s["refresh"].refresh

    def flaky(task_id, preflight_id):
        if preflight_id == second:
            raise RuntimeError("resolver down")
        return real(task_id, preflight_id)

    s["refresh"].refresh = flaky
    result = s["precompute"].precompute(task.task_id, [first, second, third])

    assert [(o.preflight_id, o.status) for o in result.outcomes] == [
        (first, PRECOMPUTE_REFRESHED), (second, PRECOMPUTE_FAILED), (third, PRECOMPUTE_REFRESHED)
    ]
    assert "resolver down" in result.outcomes[1].reasons[0]
    assert (result.refreshed_count, result.failed_count) == (2, 1)
    assert _entry(s, task, first).version == 2 and _entry(s, task, third).version == 2  # the successes were kept
    assert _entry(s, task, second).version == 1  # the failed one was left as it was


def test_unsuccessful_refresh_is_reported_as_failed():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)
    entry = _entry(s, task, current)
    s["refresh"]._reconciliation_service = type(
        "R", (), {"reconcile": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("resolver down"))}
    )()

    result = s["precompute"].precompute_active(task.task_id)

    assert result.outcomes[0].status == PRECOMPUTE_FAILED and result.outcomes[0].refresh_status == "not_refreshed"
    assert _entry(s, task, current) == entry


def test_repeated_precompute_is_idempotent():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    first = s["precompute"].precompute_active(task.task_id)
    entries = s["cache"].list_entries(task.task_id)
    analyses = len(s["analyses"])
    events = len(s["history_store"].all())
    second = s["precompute"].precompute_active(task.task_id)
    third = s["precompute"].precompute(task.task_id, [current])

    assert first.refreshed_count == 1
    assert (second.refreshed_count, second.skipped_count) == (0, 1) and third.refreshed_count == 0
    assert s["cache"].list_entries(task.task_id) == entries
    assert len(s["analyses"]) == analyses and len(s["history_store"].all()) == events


def test_newer_cache_version_is_preserved():
    s = _stack()
    task, _ = _new_task(s)
    current, _ = _add_preflight(s, task)
    s["cache"]._store._entries[(task.task_id, current)] = replace(_entry(s, task, current), version=5)  # cache is ahead
    entry = _entry(s, task, current)

    result = s["precompute"].precompute_active(task.task_id)

    assert result.outcomes[0].status == PRECOMPUTE_SKIPPED and result.outcomes[0].refresh_status == "newer_entry"
    assert s["analyses"] == [] and _entry(s, task, current) == entry


def test_explicit_preflight_ids_are_processed_in_order_without_duplicates():
    s = _stack()
    task, _ = _new_task(s)
    old, _ = _add_preflight(s, task)
    current, _ = _add_preflight(s, task, cached=False)

    result = s["precompute"].precompute(task.task_id, [old, "no-such-preflight", current, old])

    assert [o.preflight_id for o in result.outcomes] == [old, "no-such-preflight", current]
    assert _statuses(result) == {old: PRECOMPUTE_SKIPPED, "no-such-preflight": PRECOMPUTE_SKIPPED, current: PRECOMPUTE_REFRESHED}
    assert result.excluded_preflight_ids == ()


def test_precompute_never_touches_recovery_state_or_history():
    s = _stack()
    task, dep = _new_task(s)
    current, _ = _add_preflight(s, task)
    _snapshot(s, task, current)

    def state():
        return (
            s["lifecycle_service"].get(task.task_id).current_state, s["lifecycle_service"].get(dep.task_id).current_state,
            s["preflight_store"].history(task.task_id), s["dependency_service"].get_dependencies(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            s["version_service"].list_versions(task.task_id, current),
            s["preflight_invalidation_service"].get_invalidation(current),
        )

    before = state()
    s["precompute"].precompute_active(task.task_id)
    s["precompute"].precompute(task.task_id, [current])

    assert state() == before  # snapshots and version history are preserved exactly


def test_task_without_preflights_is_an_empty_result():
    s = _stack()
    result = s["precompute"].precompute_active("unknown-task")

    assert result.outcomes == () and (result.refreshed_count, result.skipped_count, result.failed_count) == (0, 0, 0)


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["precompute"].precompute(bad)
        with pytest.raises(Error):
            s["precompute"].precompute_active(bad)
    with pytest.raises(Error):
        s["precompute"].precompute("task", "not-a-list")
    with pytest.raises(Error):
        s["precompute"].precompute("task", ["ok", ""])
