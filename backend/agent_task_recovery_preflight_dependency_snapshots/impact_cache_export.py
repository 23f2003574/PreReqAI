import json
from datetime import datetime, timezone
from typing import Optional

from backend.llm.secret_redaction import LLMSecretRedactionService

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .impact_cache_consistency import (
    CORRUPTED,
    MISMATCHED,
    STALE,
    UNTRUSTED,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
)
from .impact_cache_eviction import IMPACT_CACHE_EVICTED_EVENT_TYPE
from .impact_cache_invalidation import IMPACT_CACHE_INVALIDATED_EVENT_TYPE
from .impact_cache_refresh import IMPACT_CACHE_REFRESHED_EVENT_TYPE
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheExport,
    AgentTaskRecoveryPreflightDependencyImpactCacheExportEntry,
    AgentTaskRecoveryPreflightDependencySnapshotReconciliation,
)

# The project's own export convention (backend.agent_policy_reporting,
# backend.llm.security_reports): a small closed set of formats, an explicit
# rejection of anything else, and json.dumps(to_dict(), sort_keys=True,
# indent=2, default=str) so the same result always serializes to the same
# string.
SUPPORTED_FORMATS = frozenset({"json"})

CACHED = "cached"
MISSING = "missing"
STALE_STATUS = "stale"
INVALID = "invalid"
UNAVAILABLE = "unavailable"
EXPORT_STATUSES = frozenset({CACHED, MISSING, STALE_STATUS, INVALID, UNAVAILABLE})

_redactor = LLMSecretRedactionService()


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError(ValueError):
    """Raised when export() is given invalid arguments."""


class UnsupportedFormatError(ValueError):
    """Raised when serialize() is given a format that is not supported."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheExportService:
    """A structured, read-only diagnostic snapshot of a task's cached
    dependency impact -- never a new export or storage framework (Rule):
    every field is read from persisted state through an existing service
    (the #1 cache's entries and current identity, #6's consistency check,
    the guardrails' preflight invalidation record, and the event
    histories #2/#5/#7 already append), nothing is recomputed or guessed,
    and serialization is the repository's own sorted-keys JSON convention.

    Read-only (Rule): it calls list_entries(), current_identity(),
    check() and event queries only. The one write anywhere beneath is the
    trust history append every trust validation makes (check() validates
    trust), which is history, not cache or recovery state; the cache,
    snapshots, versions, preflights and events are never changed.

    Statuses are explicit rather than inferred from absence: an entry with
    a defect in itself is INVALID (corrupted/mismatched -- the cached
    result is then reported unreadable, never echoed); one whose current
    snapshot cannot be trusted, or a preflight with no snapshot at all, is
    UNAVAILABLE; one bound to a superseded snapshot/version is STALE (its
    exact identity is kept beside the current one); no entry with a
    snapshot to build from is MISSING; otherwise CACHED. Precedence is in
    that order. Requesting a preflight that has nothing at all exports as
    UNAVAILABLE, never silently omitted.

    Deterministic (Rule): entries are ordered by preflight_id, every dict
    is serialized with sorted keys, so the same persisted state exports
    identically. Secrets: the whole export is passed through this
    repository's own LLMSecretRedactionService before it is built, so a
    secret that reached a stored reason or violation text is redacted, and
    `redaction_applied` says so.

    export() takes an optional preflight_ids for a single preflight or a
    batch; without it, every cached entry of the task plus -- with a
    preflight_store -- its current preflight. deep=True also compares each
    entry with a live snapshot diff (a live dependency read); the default
    reports only what persisted data shows.
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        consistency_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService = None,
        preflight_store=None,
        preflight_invalidation_service=None,
        event_query_service=None,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the real one.
            consistency_service: Defaults to a fresh #6 service over
                cache_service; pass the real, wired one for meaningful
                consistency and trust status.
            preflight_store: Optional, duck-typed (get(task_id) only); adds
                the current preflight to an unfiltered export so a missing
                entry for it is visible.
            preflight_invalidation_service: Optional, duck-typed
                (get_invalidation() only); enables the preflight
                invalidation fields (None without it).
            event_query_service: Optional LLMAgentTaskEventQueryService
                (query() only) over the store #2/#5/#7 append their
                history to; enables the last_*_at fields.
        """
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._consistency_service = (
            consistency_service
            if consistency_service is not None
            else LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService(cache_service=self._cache_service)
        )
        self._preflight_store = preflight_store
        self._preflight_invalidation_service = preflight_invalidation_service
        self._event_query_service = event_query_service

    def export(
        self, task_id: str, preflight_ids: Optional[list] = None, deep: bool = False
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheExport:
        """Export task_id's cached-impact state for the named preflights
        (default: all of its cached ones).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError:
                If task_id is not a non-empty string, or preflight_ids is
                given and is not a list/tuple of non-empty strings
        """
        self._require_text(task_id, "task_id")
        requested = None
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
            requested = tuple(sorted(set(preflight_ids)))

        entries = {entry.preflight_id: entry for entry in self._cache_service.list_entries(task_id)}
        if requested is not None:
            ids = list(requested)
        else:
            found = set(entries)
            current = self._preflight_store.get(task_id) if self._preflight_store is not None else None
            if current is not None:
                found.add(current.preflight_id)
            ids = sorted(found)

        raw = [self._row(task_id, preflight_id, entries.get(preflight_id), deep) for preflight_id in ids]
        redacted = _redactor.redact(raw)
        rows = tuple(
            AgentTaskRecoveryPreflightDependencyImpactCacheExportEntry(
                **{**row, "consistency": tuple(row["consistency"])}
            )
            for row in redacted
        )
        counts: dict = {}
        for row in rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        return AgentTaskRecoveryPreflightDependencyImpactCacheExport(
            task_id=task_id, requested_preflight_ids=requested, entries=rows, total=len(rows),
            status_counts=dict(sorted(counts.items())), redaction_applied=redacted != raw,
            generated_at=datetime.now(timezone.utc),
        )

    def serialize(self, export: AgentTaskRecoveryPreflightDependencyImpactCacheExport, format: str = "json") -> str:
        """Serialize an export; the same export always serializes to the
        same string.

        Raises:
            UnsupportedFormatError: If format is not one of SUPPORTED_FORMATS
        """
        if format not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"format {format!r} is not supported; must be one of {sorted(SUPPORTED_FORMATS)}"
            )
        return json.dumps(export.to_dict(), sort_keys=True, indent=2, default=str)

    def _row(self, task_id: str, preflight_id: str, entry, deep: bool) -> dict:
        identity = self._cache_service.current_identity(task_id, preflight_id)
        check = self._consistency_service.check(task_id, preflight_id, deep=deep)
        categories = {violation.category for violation in check.violations}

        if entry is not None and categories & {CORRUPTED, MISMATCHED}:
            status = INVALID
        elif identity is None or UNTRUSTED in categories:
            status = UNAVAILABLE
        elif STALE in categories:
            status = STALE_STATUS
        elif entry is None:
            status = MISSING
        else:
            status = CACHED if check.is_consistent else INVALID  # e.g. diverged from the live evidence (deep)

        invalidation = (
            self._preflight_invalidation_service.get_invalidation(preflight_id)
            if self._preflight_invalidation_service is not None
            else None
        )
        return {
            "preflight_id": preflight_id,
            "status": status,
            "snapshot_id": entry.snapshot_id if entry is not None else None,
            "version": entry.version if entry is not None else None,
            "current_snapshot_id": identity[0] if identity is not None else None,
            "current_version": identity[1] if identity is not None else None,
            "cached_at": self._iso(entry.cached_at) if entry is not None else None,
            "reconciled_at": self._iso(getattr(entry.result, "reconciled_at", None)) if entry is not None else None,
            "trust_status": "not_applicable" if identity is None else ("untrusted" if UNTRUSTED in categories else "trusted"),
            "consistency": [{"category": v.category, "reason": v.reason} for v in check.violations],
            "impact": self._impact(entry.result) if entry is not None else None,
            "preflight_invalidated": (invalidation is not None) if self._preflight_invalidation_service is not None else None,
            "preflight_invalidation_reason": invalidation.reason if invalidation is not None else None,
            "last_refreshed_at": self._last_event(task_id, preflight_id, IMPACT_CACHE_REFRESHED_EVENT_TYPE),
            "last_invalidated_at": self._last_event(task_id, preflight_id, IMPACT_CACHE_INVALIDATED_EVENT_TYPE),
            "last_evicted_at": self._last_event(task_id, preflight_id, IMPACT_CACHE_EVICTED_EVENT_TYPE),
        }

    def _last_event(self, task_id: str, preflight_id: str, event_type: str) -> Optional[str]:
        if self._event_query_service is None:
            return None
        matching = [
            event
            for event in self._event_query_service.query(task_id=task_id, event_types=[event_type])
            if isinstance(event.payload, dict) and event.payload.get("preflight_id") == preflight_id
        ]
        return self._iso(matching[-1].occurred_at) if matching else None

    @staticmethod
    def _impact(result) -> dict:
        """The cached result as plain data, or {"readable": False} -- never
        an echo of something that is not a reconciliation result."""
        if not isinstance(result, AgentTaskRecoveryPreflightDependencySnapshotReconciliation):
            return {"readable": False, "type": type(result).__name__}
        try:
            return {
                "readable": True, "status": result.status, "reliable": result.reliable, "reason": result.reason,
                "added": list(result.added), "removed": list(result.removed), "resolved": list(result.resolved),
                "blocked": list(result.blocked),
                "changed": [
                    {
                        "dependency_task_id": change.dependency_task_id,
                        "previous_state": change.previous_state, "current_state": change.current_state,
                    }
                    for change in result.changed
                ],
                "integrity_status": getattr(result.integrity, "status", None),
                "signature_status": getattr(result.signature, "status", None),
            }
        except Exception:
            return {"readable": False, "type": type(result).__name__}

    @staticmethod
    def _iso(value) -> Optional[str]:
        return value.isoformat() if isinstance(value, datetime) else None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheExportError(
                f"{field_name} is required and must be a non-empty string"
            )
