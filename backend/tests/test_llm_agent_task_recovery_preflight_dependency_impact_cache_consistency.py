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
    CONSISTENCY_MISSING,
    CORRUPTED,
    DIVERGED,
    IMPACT_CACHE_REPAIRED_EVENT_TYPE,
    KEPT_NEWER,
    MISMATCHED,
    RECOMPUTED,
    STALE,
    UNCHANGED,
    UNREPAIRABLE,
    UNTRUSTED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
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
    counted = []
    original_diff = snapshot_service.diff
    snapshot_service.diff = lambda *a, **k: (counted.append(a), original_diff(*a, **k))[1]
    consistency = None  # built below, after the reconciliation service it repairs through
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service, impact_cache_service=cache
    )
    history_store = InMemoryAgentTaskEventStore()
    consistency = LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService(
        cache_service=cache, snapshot_service=snapshot_service, reconciliation_service=reconciliation_service,
        preflight_store=preflight_store, event_service=LLMAgentTaskEventService(history_store),
    )
    reconciliation_service._impact_cache_consistency_service = consistency
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "cache": cache, "reconciliation_service": reconciliation_service,
        "consistency": consistency, "history_store": history_store, "diff_calls": counted,
    }


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def _cached(s):
    """A task with one dependency, a preflight, a snapshot, and its impact cached."""
    task, dep = _task(s["lifecycle_service"]), _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    snapshot = _snapshot(s, task, preflight_id)
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )
    s["cache"].put(task.task_id, preflight_id, plain.reconcile(task.task_id, snapshot.snapshot_id))
    return task, dep, preflight_id, snapshot


def _entry(s, task, preflight_id):
    return next(e for e in s["cache"].list_entries(task.task_id) if e.preflight_id == preflight_id)


def _overwrite(s, task, preflight_id, **changes):
    """Write straight into the store, bypassing every cache guard, to simulate corruption."""
    s["cache"]._store._entries[(task.task_id, preflight_id)] = replace(_entry(s, task, preflight_id), **changes)


def _untrust(s, snapshot):
    s["trust_service"].validate(snapshot.task_id, snapshot.snapshot_id)  # integrity baseline
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def _categories(result):
    return [v.category for v in result.violations]


def test_consistent_cache():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)

    result = s["consistency"].check(task.task_id)

    assert result.is_consistent is True and result.violations == ()
    assert result.checked_preflight_ids == (preflight_id,)
    assert s["consistency"].check(task.task_id, preflight_id).is_consistent is True


def test_stale_snapshot_detected():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    _snapshot(s, task, preflight_id)  # version 2 supersedes the entry's version 1

    result = s["consistency"].check(task.task_id, preflight_id)

    assert _categories(result) == [STALE]
    assert (result.violations[0].snapshot_id, result.violations[0].version) == (snapshot.snapshot_id, 1)


def test_changed_dependency_state_detected_only_by_deep_check():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _complete(s["lifecycle_service"], dep)  # the live graph moved on; the entry does not know

    deep = s["consistency"].check(task.task_id, preflight_id)
    cheap = s["consistency"].check(task.task_id, preflight_id, deep=False)

    assert _categories(deep) == [DIVERGED]
    assert cheap.is_consistent is True  # the cheap check reads no live dependency evidence


def test_corrupted_entries_detected():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    good = _entry(s, task, preflight_id)

    _overwrite(s, task, preflight_id, result="garbage")
    assert _categories(s["consistency"].check(task.task_id)) == [CORRUPTED]

    _overwrite(s, task, preflight_id, result=replace(good.result, status=CHANGED))  # CHANGED, but no changes recorded
    contradicted = s["consistency"].check(task.task_id)
    assert _categories(contradicted) == [CORRUPTED] and "contradicts" in contradicted.violations[0].reason

    _overwrite(s, task, preflight_id, result=replace(good.result, reliable=False))
    assert _categories(s["consistency"].check(task.task_id)) == [CORRUPTED]

    _overwrite(s, task, preflight_id, result=replace(good.result, added=None))
    assert _categories(s["consistency"].check(task.task_id)) == [CORRUPTED]


def test_mismatched_identity_detected():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    good = _entry(s, task, preflight_id)
    _overwrite(s, task, preflight_id, result=replace(good.result, snapshot_id="some-other-snapshot"))

    assert _categories(s["consistency"].check(task.task_id)) == [MISMATCHED]


def test_missing_entry_detected_for_current_preflight():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    s["cache"].invalidate(task.task_id, preflight_id)

    by_current = s["consistency"].check(task.task_id)  # the wired preflight store reveals the gap
    by_id = s["consistency"].check(task.task_id, preflight_id)

    assert _categories(by_current) == _categories(by_id) == [CONSISTENCY_MISSING]
    assert s["consistency"].check("task-with-nothing").is_consistent is True  # nothing to compute, nothing missing


def test_repair_recomputes_stale_entry_and_is_idempotent():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    newer = _snapshot(s, task, preflight_id)

    first = s["consistency"].repair(task.task_id)
    second = s["consistency"].repair(task.task_id)

    assert [a.action for a in first.actions] == [RECOMPUTED]
    assert first.before.is_consistent is False and first.is_consistent is True and first.repaired_count == 1
    assert _entry(s, task, preflight_id).snapshot_id == newer.snapshot_id
    assert second.actions == () and second.repaired_count == 0 and second.is_consistent is True
    assert _entry(s, task, preflight_id) == _entry(s, task, preflight_id)


def test_repair_fixes_diverged_corrupted_and_missing():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _complete(s["lifecycle_service"], dep)
    assert s["consistency"].repair(task.task_id).is_consistent is True
    assert _entry(s, task, preflight_id).result.status == CHANGED
    assert _entry(s, task, preflight_id).result.resolved == (dep.task_id,)

    _overwrite(s, task, preflight_id, result="garbage")
    assert [a.action for a in s["consistency"].repair(task.task_id).actions] == [RECOMPUTED]

    s["cache"].invalidate(task.task_id, preflight_id)
    repaired = s["consistency"].repair(task.task_id)
    assert repaired.before.violations[0].category == CONSISTENCY_MISSING and repaired.is_consistent is True
    assert s["cache"].get(task.task_id, preflight_id).status == CHANGED


def test_trust_failure_fails_closed_and_repair_changes_nothing():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    _untrust(s, snapshot)
    entry_before = _entry(s, task, preflight_id)
    s["diff_calls"].clear()

    check = s["consistency"].check(task.task_id, preflight_id)
    repair = s["consistency"].repair(task.task_id, preflight_id)

    assert _categories(check) == [UNTRUSTED]
    assert [a.action for a in repair.actions] == [UNREPAIRABLE]
    assert repair.repaired_count == 0 and repair.is_consistent is False
    assert _entry(s, task, preflight_id) == entry_before  # nothing recomputed, nothing removed


def test_trust_error_fails_closed():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)

    class _Broken:
        def validate(self, *a):
            raise RuntimeError("trust store offline")

    s["cache"]._trust_service = _Broken()

    assert _categories(s["consistency"].check(task.task_id, preflight_id)) == [UNTRUSTED]


def test_repair_leaves_entry_that_changed_since_the_check():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    newer = _snapshot(s, task, preflight_id)
    real_check = s["consistency"].check
    stale_check = real_check(task.task_id)  # sees the v1 entry as STALE

    # a concurrent writer recomputes a fresh, valid entry before repair acts
    s["reconciliation_service"].reconcile(task.task_id, newer.snapshot_id, use_cache=False)
    served = []
    s["consistency"].check = lambda *a, **k: (served.append(1), stale_check)[1] if not served else real_check(*a, **k)
    result = s["consistency"].repair(task.task_id)  # its first check() is the outdated one

    assert [a.action for a in result.actions] == [KEPT_NEWER]
    assert result.after.is_consistent is True
    assert _entry(s, task, preflight_id).snapshot_id == newer.snapshot_id  # the newer entry survived


def test_repair_never_overwrites_a_newer_entry_written_during_recompute():
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

    s["consistency"]._reconciliation_service = type("R", (), {"reconcile": staticmethod(racing)})()
    result = s["consistency"].repair(task.task_id)

    assert [a.action for a in result.actions] == [KEPT_NEWER]
    assert _entry(s, task, preflight_id).result.added == ("raced",)


def test_repair_history_recorded_as_references():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)

    s["consistency"].check(task.task_id)
    assert s["history_store"].all() == []  # check() is read-only

    s["consistency"].repair(task.task_id)
    (event,) = s["history_store"].list_for_task(task.task_id)
    assert event.event_type == IMPACT_CACHE_REPAIRED_EVENT_TYPE
    assert event.payload["preflight_id"] == preflight_id and event.payload["action"] == RECOMPUTED
    assert event.payload["categories"] == [STALE]
    s["consistency"].repair(task.task_id)
    assert len(s["history_store"].list_for_task(task.task_id)) == 1  # a no-op repair records nothing


def test_failing_history_never_blocks_repair():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)

    class _Broken:
        def emit(self, *a, **k):
            raise RuntimeError("event store offline")

    s["consistency"]._event_service = _Broken()

    assert s["consistency"].repair(task.task_id).is_consistent is True


def test_inconsistent_entry_falls_back_to_fresh_analysis_on_consumption():
    s = _stack()
    task, _, preflight_id, snapshot = _cached(s)
    good = _entry(s, task, preflight_id)
    _overwrite(s, task, preflight_id, result=replace(good.result, status=CHANGED))  # CHANGED with no changes: contradiction
    s["diff_calls"].clear()

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED  # the corrupted entry was NOT served
    assert s["diff_calls"]  # a fresh analysis ran instead


def test_consistent_entry_is_served_at_no_extra_live_read_cost():
    s = _stack()
    task, _, _, snapshot = _cached(s)
    service = s["reconciliation_service"]._impact_cache_consistency_service

    s["reconciliation_service"]._impact_cache_consistency_service = None
    s["diff_calls"].clear()
    service_off = service and s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    baseline = len(s["diff_calls"])  # the cache's own trust gate already reads live

    s["reconciliation_service"]._impact_cache_consistency_service = service
    s["diff_calls"].clear()
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == service_off.status == UNCHANGED
    assert len(s["diff_calls"]) == baseline  # the consistency check added none


def test_consistency_failure_on_consumption_falls_back_to_fresh_analysis():
    s = _stack()
    task, _, _, snapshot = _cached(s)

    class _Broken:
        def check(self, *a, **k):
            raise RuntimeError("consistency unavailable")

    s["reconciliation_service"]._impact_cache_consistency_service = _Broken()
    s["diff_calls"].clear()

    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED
    assert s["diff_calls"]  # fail closed: recomputed rather than trusting an unchecked entry


def test_check_is_read_only_and_repair_never_touches_recovery_state():
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

    entries = s["cache"].list_entries(task.task_id)
    before = state()
    s["consistency"].check(task.task_id)
    s["consistency"].check(task.task_id)
    assert s["cache"].list_entries(task.task_id) == entries  # check() changed nothing

    s["consistency"].repair(task.task_id)
    assert state() == before


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["consistency"].check(bad)
        with pytest.raises(Error):
            s["consistency"].repair(bad)
    with pytest.raises(Error):
        s["consistency"].check("task", "")
    with pytest.raises(Error):
        s["consistency"].repair("task", 5)
