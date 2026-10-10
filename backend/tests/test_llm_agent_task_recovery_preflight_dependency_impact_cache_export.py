import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
import json

from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventQueryService, LLMAgentTaskEventService
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    ImpactCacheExportUnsupportedFormatError,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheExportService,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
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
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    history_service = LLMAgentTaskEventService(history_store)
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, event_service=history_service
    )
    eviction = LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService(
        cache_service=cache, invalidation_service=invalidation, event_service=history_service
    )
    export = LLMAgentTaskRecoveryPreflightDependencyImpactCacheExportService(
        cache_service=cache, consistency_service=consistency, preflight_store=preflight_store,
        preflight_invalidation_service=preflight_invalidation_service,
        event_query_service=LLMAgentTaskEventQueryService(history_store),
    )
    return {
        "export": export, "invalidation": invalidation, "eviction": eviction,
        "preflight_invalidation_service": preflight_invalidation_service, "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
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


def _add(s, task, cached=True):
    """Another preflight for task with a snapshot and, optionally, a cached entry."""
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)
    snapshot = _snapshot(s, task, preflight_id)
    if cached:
        plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
            snapshot_service=s["snapshot_service"], version_service=s["version_service"]
        )
        s["cache"].put(task.task_id, preflight_id, plain.reconcile(task.task_id, snapshot.snapshot_id))
    return preflight_id, snapshot


def _row(result, preflight_id):
    return next(e for e in result.entries if e.preflight_id == preflight_id)


def test_complete_export_of_a_consistent_entry():
    s = _stack()
    task, dep, preflight_id, snapshot = _cached(s)
    entry = _entry(s, task, preflight_id)

    result = s["export"].export(task.task_id)
    row = _row(result, preflight_id)

    assert (result.task_id, result.total, result.status_counts) == (task.task_id, 1, {"cached": 1})
    assert row.status == "cached" and row.trust_status == "trusted" and row.consistency == ()
    assert (row.snapshot_id, row.version) == (snapshot.snapshot_id, 1)  # exact identity, entry and source alike
    assert (row.current_snapshot_id, row.current_version) == (snapshot.snapshot_id, 1)
    assert row.cached_at == entry.cached_at.isoformat() and row.reconciled_at == entry.result.reconciled_at.isoformat()
    assert row.impact["readable"] is True and row.impact["status"] == UNCHANGED and row.impact["reliable"] is True
    assert row.impact["added"] == [] and row.impact["changed"] == []
    assert row.preflight_invalidated is False and row.preflight_invalidation_reason is None
    assert (row.last_refreshed_at, row.last_invalidated_at, row.last_evicted_at) == (None, None, None)


def test_export_carries_impact_changes_and_history_state():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _complete(s["lifecycle_service"], dep)
    s["refresh"].refresh(task.task_id, preflight_id)  # rebuilds it: one refresh event
    s["invalidation"].invalidate_for_preflight(task.task_id, preflight_id)  # then drops it: one invalidation event
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")

    row = _row(s["export"].export(task.task_id, [preflight_id]), preflight_id)

    assert row.status == "missing" and row.impact is None  # the entry is gone, said explicitly
    assert row.last_refreshed_at and row.last_invalidated_at and row.last_evicted_at is None
    assert row.preflight_invalidated is True and row.preflight_invalidation_reason == "operator judgment"


def test_evicted_state_comes_from_recorded_history():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)  # obsolete
    s["eviction"].evict(task.task_id)

    row = _row(s["export"].export(task.task_id, [preflight_id]), preflight_id)

    assert row.status == "missing" and row.last_evicted_at is not None


def test_changed_dependency_state_is_exported_with_the_deep_check():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _complete(s["lifecycle_service"], dep)

    persisted = _row(s["export"].export(task.task_id), preflight_id)
    deep = _row(s["export"].export(task.task_id, deep=True), preflight_id)

    assert persisted.status == "cached"  # persisted data alone shows nothing wrong
    assert deep.status == "invalid" and deep.consistency[0]["category"] == "diverged"


def test_missing_stale_invalid_and_unavailable_entries_are_explicit():
    s = _stack()
    task, _, stale, _ = _cached(s)
    _snapshot(s, task, stale)  # stale
    invalid, _ = _add(s, task)
    good = _entry(s, task, invalid)
    s["cache"]._store._entries[(task.task_id, invalid)] = replace(good, result="garbage")  # corrupted
    missing, _ = _add(s, task, cached=False)
    untrusted, untrusted_snapshot = _add(s, task)
    _untrust(s, untrusted_snapshot)
    no_snapshot = _new_preflight(s["preflight_store"], task.task_id)

    result = s["export"].export(task.task_id, [stale, invalid, missing, untrusted, no_snapshot, "no-such-preflight"])

    statuses = {e.preflight_id: e.status for e in result.entries}
    assert statuses == {
        stale: "stale", invalid: "invalid", missing: "missing", untrusted: "unavailable",
        no_snapshot: "unavailable", "no-such-preflight": "unavailable",
    }
    assert result.status_counts == {"invalid": 1, "missing": 1, "stale": 1, "unavailable": 3}
    stale_row = _row(result, stale)
    assert stale_row.version == 1 and stale_row.current_version == 2  # both identities preserved exactly
    assert _row(result, invalid).impact == {"readable": False, "type": "str"}  # never echoed
    untrusted_row = _row(result, untrusted)
    assert untrusted_row.trust_status == "untrusted" and untrusted_row.snapshot_id is not None  # entry kept visible
    assert _row(result, no_snapshot).trust_status == "not_applicable"
    assert _row(result, missing).snapshot_id is None and _row(result, missing).current_snapshot_id is not None


def test_partial_data_without_optional_collaborators():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    bare = LLMAgentTaskRecoveryPreflightDependencyImpactCacheExportService(
        cache_service=s["cache"], consistency_service=s["consistency"]
    )

    row = _row(bare.export(task.task_id), preflight_id)

    assert row.status == "cached" and row.preflight_invalidated is None  # unknown is None, not False
    assert (row.last_refreshed_at, row.last_invalidated_at, row.last_evicted_at) == (None, None, None)


def test_ordering_is_deterministic():
    s = _stack()
    task, _, first, _ = _cached(s)
    others = [_add(s, task)[0] for _ in range(3)]
    ids = [first] + others

    forward = s["export"].export(task.task_id, ids)
    backward = s["export"].export(task.task_id, list(reversed(ids)))
    default = s["export"].export(task.task_id)

    assert [e.preflight_id for e in forward.entries] == sorted(ids) == [e.preflight_id for e in backward.entries]
    assert [e.preflight_id for e in default.entries] == sorted(ids)
    text = s["export"].serialize(forward)
    assert text == s["export"].serialize(forward)  # the same export always serializes to the same string
    assert json.loads(text)["entries"] == json.loads(s["export"].serialize(backward))["entries"]
    assert text.index('"entries"') < text.index('"generated_at"') and json.loads(text)["task_id"] == task.task_id


def test_secrets_are_redacted():
    s = _stack()
    task, _, preflight_id, _ = _cached(s)
    secret = "sk-abcdefghij1234567890"
    entry = _entry(s, task, preflight_id)
    s["cache"]._store._entries[(task.task_id, preflight_id)] = replace(
        entry, result=replace(entry.result, reason=f"resolver failed, api_key={secret}")
    )

    clean = s["export"].export(task.task_id)
    text = s["export"].serialize(clean)

    assert clean.redaction_applied is True
    assert secret not in text and secret not in str(clean.to_dict())
    assert _row(clean, preflight_id).impact["reason"] != f"resolver failed, api_key={secret}"
    assert _stack_export_without_secrets(s, task).redaction_applied is False


def _stack_export_without_secrets(s, task):
    other = _stack()
    other_task, _, _, _ = _cached(other)
    return other["export"].export(other_task.task_id)


def test_single_and_batch_exports():
    s = _stack()
    task, _, first, _ = _cached(s)
    second, _ = _add(s, task)

    single = s["export"].export(task.task_id, [second])
    batch = s["export"].export(task.task_id, [first, second])

    assert [e.preflight_id for e in single.entries] == [second] and single.requested_preflight_ids == (second,)
    assert {e.preflight_id for e in batch.entries} == {first, second} and batch.total == 2
    assert _row(single, second) == _row(batch, second)


def test_empty_results():
    s = _stack()
    task = _task(s["lifecycle_service"])

    unknown = s["export"].export("task-without-anything")
    no_entries = s["export"].export(task.task_id, [])

    for result in (unknown, no_entries):
        assert result.entries == () and result.total == 0 and result.status_counts == {}
        assert result.redaction_applied is False
    assert json.loads(s["export"].serialize(unknown))["entries"] == []


def test_export_never_changes_cache_or_recovery_state():
    s = _stack()
    task, dep, preflight_id, _ = _cached(s)
    _snapshot(s, task, preflight_id)  # stale, so an export has plenty it could be tempted to fix
    extra, _ = _add(s, task, cached=False)

    def state():
        return (
            s["cache"].list_entries(task.task_id), len(s["history_store"].all()),
            s["lifecycle_service"].get(task.task_id).current_state, s["lifecycle_service"].get(dep.task_id).current_state,
            s["preflight_store"].history(task.task_id), s["dependency_service"].get_dependencies(task.task_id),
            [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)],
            s["version_service"].list_versions(task.task_id, preflight_id),
            s["preflight_invalidation_service"].get_invalidation(preflight_id),
        )

    before = state()
    for _ in range(3):
        s["export"].export(task.task_id)
        s["export"].export(task.task_id, [preflight_id, extra], deep=True)

    assert state() == before and s["analyses"] == []  # nothing repaired, refreshed, evicted or recomputed


def test_serialize_rejects_unsupported_formats():
    s = _stack()
    result = s["export"].export("any-task")

    with pytest.raises(ImpactCacheExportUnsupportedFormatError):
        s["export"].serialize(result, format="xml")


def test_validation():
    s = _stack()
    Error = InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError
    for bad in ("", None, 5):
        with pytest.raises(Error):
            s["export"].export(bad)
    with pytest.raises(Error):
        s["export"].export("task", "not-a-list")
    with pytest.raises(Error):
        s["export"].export("task", ["ok", ""])
