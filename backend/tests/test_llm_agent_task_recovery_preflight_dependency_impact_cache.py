from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY as TASK_READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    INDETERMINATE,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(lifecycle_service):
    return lifecycle_service.create({"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"})


def _complete(lifecycle_service, task):
    for target in (PLANNED, TASK_READY, RUNNING, COMPLETED):
        lifecycle_service.transition(task.task_id, target)


def _preflight_id(preflight_store, task_id):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=ALLOW,
        blocking_reasons=(), warnings=(), checked_at=NOW,
    )
    return preflight_store.save(result).preflight_id


class _CountingSnapshotService(LLMAgentTaskRecoveryPreflightDependencySnapshotService):
    """Counts live diff() calls -- the work a cache hit must skip."""

    diffs = 0

    def diff(self, task_id, snapshot_id):
        self.diffs += 1
        return super().diff(task_id, snapshot_id)


def _stack(versioned=True, trusted=True, cache_trust=True):
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = _CountingSnapshotService(dependency_resolver=dependency_resolver, preflight_store=preflight_store)
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
    cache = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=snapshot_service, version_service=version_service,
        trust_service=trust_service if cache_trust else None,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service, version_service=version_service,
        trust_service=trust_service if trusted else None, impact_cache_service=cache,
    )
    return {
        "lifecycle_service": lifecycle_service, "dependency_service": dependency_service,
        "preflight_store": preflight_store, "snapshot_service": snapshot_service,
        "version_service": version_service, "trust_service": trust_service,
        "cache": cache, "reconciliation_service": reconciliation_service,
    }


def _snapshot(s, with_dependency=True):
    task = _task(s["lifecycle_service"])
    dep = _task(s["lifecycle_service"])
    if with_dependency:
        s["dependency_service"].add_dependency(task.task_id, dep.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    if s["version_service"] is not None:
        s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    return task, dep, preflight_id, snapshot


def test_miss_then_put_then_hit():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    assert s["cache"].get(task.task_id, preflight_id) is None

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    cached = s["cache"].get(task.task_id, preflight_id)

    assert cached == result
    assert cached.status == UNCHANGED
    assert cached.version == 1


def test_hit_skips_fresh_impact_analysis():
    s = _stack(cache_trust=False, trusted=False)
    task, _, _, snapshot = _snapshot(s)

    first = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    diffs_after_first = s["snapshot_service"].diffs
    second = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert second == first
    assert s["snapshot_service"].diffs == diffs_after_first


def test_no_cache_preserves_existing_behavior():
    s = _stack(cache_trust=False, trusted=False)
    task, _, _, snapshot = _snapshot(s)
    plain = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )

    cached_path = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    plain_result = plain.reconcile(task.task_id, snapshot.snapshot_id)

    assert replace(plain_result, reconciled_at=cached_path.reconciled_at) == cached_path


def test_exact_snapshot_version_matching():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert s["cache"].get(task.task_id, preflight_id) == result

    # A new snapshot version supersedes the cached entry with no notification.
    second = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, second)

    assert s["cache"].get(task.task_id, preflight_id) is None


def test_put_refuses_result_for_superseded_snapshot():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    second = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, second)
    s["cache"].invalidate(task.task_id, preflight_id)

    assert s["cache"].put(task.task_id, preflight_id, result) is None
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_put_refuses_unversioned_result_when_versioning_configured():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert s["cache"].put(task.task_id, preflight_id, replace(result, version=None)) is None


def test_unversioned_stack_matches_on_snapshot_id():
    s = _stack(versioned=False)
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert s["cache"].get(task.task_id, preflight_id) == result

    s["snapshot_service"].create(task.task_id, preflight_id)

    assert s["cache"].get(task.task_id, preflight_id) is None


def test_dependency_change_invalidates_entry():
    s = _stack(cache_trust=False, trusted=False)
    task, dep, preflight_id, snapshot = _snapshot(s)
    assert s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id).status == UNCHANGED

    _complete(s["lifecycle_service"], dep)  # live change the cache cannot see on its own
    stale = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert stale.status == UNCHANGED  # documented sharp edge: still cached

    invalidation = s["cache"].invalidate(task.task_id, preflight_id, reason="dependency completed")
    fresh = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert invalidation.invalidated is True
    assert invalidation.reason == "dependency completed"
    assert fresh.status == CHANGED
    assert fresh.resolved == (dep.task_id,)
    assert s["cache"].get(task.task_id, preflight_id) == fresh


def test_untrusted_snapshot_never_served_from_cache():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # integrity baseline
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert s["cache"].get(task.task_id, preflight_id) == result

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    assert s["cache"].get(task.task_id, preflight_id) is None
    after = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert after.status == INDETERMINATE
    assert after.reliable is False


def test_integrity_only_validation_blocks_cache():
    s = _stack()
    integrity_only = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"],
        integrity_service=LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(
            snapshot_service=s["snapshot_service"], version_service=s["version_service"]
        ),
    )
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    assert integrity_only.put(task.task_id, preflight_id, result) is not None
    assert integrity_only.get(task.task_id, preflight_id) == result

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    assert integrity_only.get(task.task_id, preflight_id) is None


def test_trust_service_error_fails_closed():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    class _Broken:
        def validate(self, task_id, snapshot_id):
            raise RuntimeError("trust store offline")

    broken = LLMAgentTaskRecoveryPreflightDependencyImpactCacheService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"], trust_service=_Broken()
    )
    assert broken.put(task.task_id, preflight_id, result) is not None
    assert broken.get(task.task_id, preflight_id) is None


def test_indeterminate_result_is_not_cached():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    unreliable = replace(result, status=INDETERMINATE, reliable=False, reason="boom")
    s["cache"].invalidate(task.task_id, preflight_id)

    assert s["cache"].put(task.task_id, preflight_id, unreliable) is None
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_put_is_idempotent():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    first = s["cache"].put(task.task_id, preflight_id, result)
    again = s["cache"].put(task.task_id, preflight_id, replace(result, reconciled_at=NOW))

    assert again == first
    assert again.cached_at == first.cached_at
    assert s["cache"].get(task.task_id, preflight_id) == result


def test_put_replaces_entry_when_content_differs():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    changed = replace(result, status=CHANGED, added=("new-dep",))

    s["cache"].put(task.task_id, preflight_id, changed)

    assert s["cache"].get(task.task_id, preflight_id) == changed


def test_invalidate_is_idempotent():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    first = s["cache"].invalidate(task.task_id, preflight_id)
    second = s["cache"].invalidate(task.task_id, preflight_id)
    never_cached = s["cache"].invalidate(task.task_id, "no-such-preflight")

    assert first.invalidated is True
    assert second.invalidated is False
    assert never_cached.invalidated is False
    assert s["cache"].get(task.task_id, preflight_id) is None


def test_get_never_mutates_recovery_state():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    before = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["snapshot_service"]._store.list_for_task(task.task_id),
        s["version_service"].list_versions(task.task_id, preflight_id),
        s["preflight_store"].history(task.task_id),
    )

    for _ in range(3):
        s["cache"].get(task.task_id, preflight_id)
        s["cache"].get(task.task_id, "unknown-preflight")

    after = (
        s["lifecycle_service"].get(task.task_id).current_state,
        s["snapshot_service"]._store.list_for_task(task.task_id),
        s["version_service"].list_versions(task.task_id, preflight_id),
        s["preflight_store"].history(task.task_id),
    )
    assert after == before


def test_cache_get_failure_falls_back_to_fresh_analysis():
    s = _stack(trusted=False)

    class _Exploding:
        def get(self, task_id, preflight_id):
            raise RuntimeError("cache down")

        def put(self, task_id, preflight_id, result):
            raise RuntimeError("cache down")

    reconciliation = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"], impact_cache_service=_Exploding()
    )
    task, _, _, snapshot = _snapshot(s)

    result = reconciliation.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert result.reliable is True


def test_reconcile_of_older_snapshot_does_not_use_newer_entry():
    s = _stack(cache_trust=False, trusted=False)
    task, _, preflight_id, first = _snapshot(s)
    second = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, second)
    latest_result = s["reconciliation_service"].reconcile(task.task_id, second.snapshot_id)

    older = s["reconciliation_service"].reconcile(task.task_id, first.snapshot_id)

    assert older.snapshot_id == first.snapshot_id
    assert s["cache"].get(task.task_id, preflight_id) == latest_result


def test_validation():
    s = _stack()
    task, _, preflight_id, snapshot = _snapshot(s)
    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    for bad in ("", None, 5):
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
            s["cache"].get(bad, preflight_id)
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
            s["cache"].get(task.task_id, bad)
        with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
            s["cache"].invalidate(bad, preflight_id)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
        s["cache"].invalidate(task.task_id, preflight_id, reason=5)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
        s["cache"].put(task.task_id, preflight_id, "not a result")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
        s["cache"].put("other-task", preflight_id, result)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencyImpactCacheError):
        s["cache"].put(task.task_id, "other-preflight", result)
