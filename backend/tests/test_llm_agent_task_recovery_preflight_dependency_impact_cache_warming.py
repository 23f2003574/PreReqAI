import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import (
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
    ALREADY_CURRENT,
    CHANGED,
    NOT_CACHED,
    SKIPPED,
    UNCHANGED,
    WARMED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService,
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
    # store.save() is idempotent for identical content, so each preflight must differ
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=decision, blocking_reasons=(),
        warnings=(f"run-{next(_counter)}",), checked_at=NOW + timedelta(microseconds=next(_counter)),
    )
    return preflight_store.save(result).preflight_id


def _stack(versioned=False, trusted=True):
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    version_service = (
        LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService(snapshot_service=snapshot_service)
        if versioned else None
    )
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(
        snapshot_service=snapshot_service, version_service=version_service
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service, version_service=version_service
    )
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    event_store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(event_store)
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service
    )
    invalidation = LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService(
        cache_service=cache, snapshot_service=snapshot_service, dependency_service=dependency_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
        event_query_service=LLMAgentTaskEventQueryService(event_store),
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service,
        impact_cache_service=cache, impact_cache_invalidation_service=invalidation,
    )
    calls = []
    original = reconciliation_service.reconcile
    reconciliation_service.reconcile = lambda *a, **k: (calls.append(a), original(*a, **k))[1]
    warming = LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService(
        cache_service=cache, reconciliation_service=reconciliation_service, snapshot_service=snapshot_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
        version_service=version_service, trust_service=trust_service if trusted else None,
        invalidation_service=invalidation,
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service, "version_service": version_service,
        "trust_service": trust_service, "preflight_invalidation_service": preflight_invalidation_service,
        "event_service": event_service, "cache": cache, "reconciliation_service": reconciliation_service,
        "analysis_calls": calls, "warming": warming,
    }


def _prepared(s, decision=ALLOW, with_dependency=True):
    """A task with one dependency, one preflight, and a snapshot of it."""
    task = _task(s["lifecycle_service"])
    dep = _task(s["lifecycle_service"])
    if with_dependency:
        s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _new_preflight(s["preflight_store"], task.task_id, decision)
    snapshot = _snapshot(s, task, preflight_id)
    return task, dep, preflight_id, snapshot


def _snapshot(s, task, preflight_id):
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    if s["version_service"] is not None:
        s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return snapshot


def test_warms_valid_current_preflight():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == WARMED
    assert result.replaced is False
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.impact_status == UNCHANGED
    assert s["cache"].get(task.task_id, preflight_id).snapshot_id == snapshot.snapshot_id


def test_normal_validation_path_uses_warmed_entry():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    s["warming"].warm(task.task_id, preflight_id)
    analyses = len(s["analysis_calls"])
    diffs = []
    original = s["snapshot_service"].diff
    s["snapshot_service"].diff = lambda *a, **k: (diffs.append(1), original(*a, **k))[1]

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert result.status == UNCHANGED
    assert diffs == []  # served from the warmed entry, no fresh analysis
    assert len(s["analysis_calls"]) == analyses + 1


def test_versioned_stack_records_exact_version():
    s = _stack(versioned=True)
    task, _, preflight_id, _ = _prepared(s)

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == WARMED
    assert result.version == 1
    assert s["cache"].get(task.task_id, preflight_id).version == 1


def test_already_current_entry_is_skipped_without_analysis():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)
    s["warming"].warm(task.task_id, preflight_id)
    entry = s["cache"].list_entries(task.task_id)[0]
    analyses = len(s["analysis_calls"])

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == ALREADY_CURRENT
    assert len(s["analysis_calls"]) == analyses
    assert s["cache"].list_entries(task.task_id)[0] == entry


def test_stale_entry_from_replaced_snapshot_is_replaced():
    s = _stack(versioned=True)
    task, _, preflight_id, first = _prepared(s)
    s["warming"].warm(task.task_id, preflight_id)
    second = _snapshot(s, task, preflight_id)

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == WARMED
    assert result.replaced is True
    assert (result.snapshot_id, result.version) == (second.snapshot_id, 2)
    assert s["cache"].get(task.task_id, preflight_id).snapshot_id == second.snapshot_id


def test_stale_entry_from_dependency_event_is_replaced():
    s = _stack()
    task, dep, preflight_id, _ = _prepared(s)
    s["warming"].warm(task.task_id, preflight_id)
    _complete(s["lifecycle_service"], dep)
    s["event_service"].emit(dep.task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == WARMED
    assert result.replaced is True
    assert result.impact_status == CHANGED
    assert s["cache"].get(task.task_id, preflight_id).status == CHANGED


def test_untrusted_snapshot_is_never_warmed():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # integrity baseline
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == SKIPPED
    assert "not trusted" in result.reasons[0]
    assert s["analysis_calls"] == []
    assert s["cache"].list_entries(task.task_id) == []


def test_trust_service_error_fails_closed():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)

    class _Broken:
        def validate(self, task_id, snapshot_id):
            raise RuntimeError("trust store offline")

    s["warming"]._trust_service = _Broken()
    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == SKIPPED
    assert "could not be verified" in result.reasons[0]
    assert s["cache"].list_entries(task.task_id) == []


def test_superseded_preflight_is_not_warmed():
    s = _stack()
    task, _, old_preflight, _ = _prepared(s)
    _new_preflight(s["preflight_store"], task.task_id)  # a newer preflight supersedes it

    result = s["warming"].warm(task.task_id, old_preflight)

    assert result.status == SKIPPED
    assert "current preflight" in result.reasons[0]
    assert s["analysis_calls"] == []


def test_invalidated_denied_and_unknown_preflights_are_skipped():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="operator judgment")
    invalidated = s["warming"].warm(task.task_id, preflight_id)
    assert invalidated.status == SKIPPED and "operator judgment" in invalidated.reasons[0]

    denied_task, _, denied_preflight, _ = _prepared(s, decision=DENY)
    assert "deny" in s["warming"].warm(denied_task.task_id, denied_preflight).reasons[0]

    assert s["warming"].warm(task.task_id, "no-such-preflight").status == SKIPPED
    assert s["analysis_calls"] == []


def test_preflight_without_snapshot_is_skipped_and_none_is_captured():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _new_preflight(s["preflight_store"], task.task_id)

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == SKIPPED
    assert "no dependency snapshot" in result.reasons[0]
    assert s["snapshot_service"].latest_for_preflight(task.task_id, preflight_id) is None


def test_stale_freshness_skips_warming():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)

    class _Freshness:
        def check(self, task_id, preflight=None):
            return type("F", (), {"is_fresh": False, "stale_reasons": ("task state changed",)})()

    s["warming"]._freshness_service = _Freshness()
    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == SKIPPED
    assert "task state changed" in result.reasons[0]


def test_analysis_failure_is_not_cached():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)
    s["warming"]._reconciliation_service = type(
        "R", (), {"reconcile": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("resolver down"))}
    )()

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == NOT_CACHED
    assert "resolver down" in result.reasons[0]
    assert s["cache"].list_entries(task.task_id) == []


def test_unreliable_analysis_is_not_cached():
    s = _stack(trusted=False)
    task, _, preflight_id, snapshot = _prepared(s)
    s["reconciliation_service"]._trust_service = type(
        "T", (), {"validate": lambda self, t, sid: type("R", (), {"trusted": False, "blocking_reasons": ("bad",)})()}
    )()

    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == NOT_CACHED
    assert result.impact_status == "indeterminate"
    assert s["cache"].list_entries(task.task_id) == []


def test_older_evidence_never_overwrites_newer_entry():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    older = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    s["cache"].invalidate(task.task_id, preflight_id)
    newer = replace(older, status=CHANGED, added=("late-dep",), reconciled_at=older.reconciled_at + timedelta(seconds=5))
    s["cache"].put(task.task_id, preflight_id, newer)

    kept = s["cache"].put(task.task_id, preflight_id, older)

    assert kept.result == newer
    assert s["cache"].get(task.task_id, preflight_id) == newer


def test_warm_reports_newer_entry_that_wins_a_race():
    s = _stack()
    task, _, preflight_id, snapshot = _prepared(s)
    real = s["reconciliation_service"].reconcile

    def racing_reconcile(task_id, snapshot_id, **kwargs):
        result = real(task_id, snapshot_id, **kwargs)
        s["cache"].invalidate(task_id, preflight_id)
        newer = replace(result, added=("raced-dep",), status=CHANGED, reconciled_at=result.reconciled_at + timedelta(seconds=5))
        s["cache"].put(task_id, preflight_id, newer)  # a concurrent, newer computation lands first
        return result

    s["warming"]._reconciliation_service = type("R", (), {"reconcile": staticmethod(racing_reconcile)})()
    result = s["warming"].warm(task.task_id, preflight_id)

    assert result.status == ALREADY_CURRENT
    assert "newer entry" in result.reasons[0]
    assert s["cache"].get(task.task_id, preflight_id).added == ("raced-dep",)


def test_warm_active_processes_only_relevant_preflights():
    s = _stack()
    task, _, first_preflight, _ = _prepared(s)
    second_preflight = _new_preflight(s["preflight_store"], task.task_id)
    _snapshot(s, task, second_preflight)

    summary = s["warming"].warm_active(task.task_id)

    assert [r.preflight_id for r in summary.results] == [second_preflight, first_preflight]  # newest first
    assert [r.status for r in summary.results] == [WARMED, SKIPPED]
    assert (summary.warmed_count, summary.skipped_count) == (1, 1)
    assert summary.excluded_preflight_ids == ()
    assert [e.preflight_id for e in s["cache"].list_entries(task.task_id)] == [second_preflight]


def test_warm_active_excludes_invalidated_preflights():
    s = _stack()
    task, _, first_preflight, _ = _prepared(s)
    second_preflight = _new_preflight(s["preflight_store"], task.task_id)
    _snapshot(s, task, second_preflight)
    s["preflight_invalidation_service"].invalidate(task.task_id, reason="stale plan")

    summary = s["warming"].warm_active(task.task_id)

    assert summary.excluded_preflight_ids == (second_preflight,)
    assert [r.preflight_id for r in summary.results] == [first_preflight]
    assert summary.warmed_count == 0
    assert s["cache"].list_entries(task.task_id) == []


def test_warm_active_is_scoped_to_one_task():
    s = _stack()
    task, _, preflight_id, _ = _prepared(s)
    other, _, other_preflight, _ = _prepared(s)

    s["warming"].warm_active(task.task_id)

    assert [e.preflight_id for e in s["cache"].list_entries(task.task_id)] == [preflight_id]
    assert s["cache"].list_entries(other.task_id) == []


def test_repeated_warming_is_idempotent():
    s = _stack()
    task, _, first_preflight, _ = _prepared(s)
    second_preflight = _new_preflight(s["preflight_store"], task.task_id)
    _snapshot(s, task, second_preflight)

    first = s["warming"].warm_active(task.task_id)
    entries = s["cache"].list_entries(task.task_id)
    analyses = len(s["analysis_calls"])
    second = s["warming"].warm_active(task.task_id)
    third = s["warming"].warm(task.task_id, second_preflight)

    assert first.warmed_count == 1
    assert (second.warmed_count, second.already_current_count, second.skipped_count) == (0, 1, 1)
    assert third.status == ALREADY_CURRENT
    assert s["cache"].list_entries(task.task_id) == entries
    assert len(s["analysis_calls"]) == analyses


def test_warming_never_mutates_recovery_state():
    s = _stack()
    task, dep, preflight_id, _ = _prepared(s)
    snapshot_ids = lambda: [x.snapshot_id for x in s["snapshot_service"]._store.list_for_task(task.task_id)]
    before = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["lifecycle_service"].get(dep.task_id).current_state,
        s["preflight_store"].history(task.task_id),
        s["dependency_service"].get_dependencies(task.task_id),
        snapshot_ids(),
        s["preflight_invalidation_service"].get_invalidation(preflight_id),
    )

    s["warming"].warm_active(task.task_id)
    s["warming"].warm(task.task_id, preflight_id)

    after = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["lifecycle_service"].get(dep.task_id).current_state,
        s["preflight_store"].history(task.task_id),
        s["dependency_service"].get_dependencies(task.task_id),
        snapshot_ids(),
        s["preflight_invalidation_service"].get_invalidation(preflight_id),
    )
    assert after == before


def test_validation():
    s = _stack()
    for bad in ("", None, 5):
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError):
            s["warming"].warm(bad, "preflight")
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError):
            s["warming"].warm("task", bad)
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError):
            s["warming"].warm_active(bad)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheWarmingError):
        LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService().warm_active("task")
