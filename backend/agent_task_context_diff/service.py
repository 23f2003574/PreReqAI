from backend.agent_task_context_snapshots import LLMAgentTaskContextSnapshotService

from .models import TaskContextDiff


class InvalidTaskContextDiffError(ValueError):
    """Raised when diff() is given a missing/blank task_id, or a
    from_version/to_version that is neither an int nor a string."""


class UnknownTaskContextVersionError(KeyError):
    """Raised when from_version/to_version names a context_version that
    was never snapshotted for task_id."""


class CrossTaskDiffError(ValueError):
    """Raised when from_version/to_version is given as a snapshot_id
    belonging to a task other than task_id."""


class LLMAgentTaskContextDiffService:
    """Compares two persisted Commit #10 TaskContextSnapshot records for
    one task and reports exactly what changed.

    Not a second reconciliation engine: unlike Commit #8's
    LLMAgentTaskContextReconciler (which compares stored context against
    a *live* resolution -- retrieval, selection, authorization,
    freshness, all reused from elsewhere), this service only ever reads
    two already-persisted, immutable snapshots (Rule: "compare persisted
    versions/snapshots, not live context") and compares their own
    resolved_context/provenance directly -- a plain equality diff, the
    same "no dedicated diff module exists in this repository, so a
    direct comparison on already-materialized values is the literal
    reuse available" reasoning Commit #8 already established. No
    retrieval, selection, authorization, or freshness service is called
    here at all.

    from_version/to_version each accept either an int (looked up as that
    context_version within task_id's own snapshot history, via Commit
    #10's own LLMAgentTaskContextSnapshotService.list()) or a str
    (treated as a snapshot_id and fetched via Commit #10's own get(),
    then checked against task_id -- Rule: "reject versions belonging to
    another task"). Both forms resolve to the exact same underlying
    TaskContextSnapshot; the Result's own from_version/to_version fields
    always report the resolved context_version integer either way.

    diff() only ever reads LLMAgentTaskContextSnapshotService.get()/
    list() -- nothing here calls refresh(), restore(), or any other
    method that could write to a task context, project context, or
    memory store (Rule: "read-only; no refresh, restore, or mutation").
    """

    def __init__(self, snapshot_service: LLMAgentTaskContextSnapshotService):
        self._snapshot_service = snapshot_service

    def diff(self, task_id: str, from_version, to_version) -> TaskContextDiff:
        """Compare from_version against to_version for task_id.

        Raises:
            InvalidTaskContextDiffError: If task_id is missing/blank, or
                from_version/to_version is neither an int nor a string
            UnknownTaskContextSnapshotError: If a snapshot_id form names
                a snapshot that was never created (propagated from
                Commit #10's own get(), unwrapped)
            UnknownTaskContextVersionError: If an int form names a
                context_version never snapshotted for task_id
            CrossTaskDiffError: If a snapshot_id form belongs to a
                different task
        """
        self._validate(task_id, from_version, to_version)

        from_snapshot = self._resolve_snapshot(task_id, from_version)
        to_snapshot = self._resolve_snapshot(task_id, to_version)

        from_by_id = self._entries_by_id(from_snapshot)
        to_by_id = self._entries_by_id(to_snapshot)
        from_provenance_by_id = self._provenance_by_id(from_snapshot)
        to_provenance_by_id = self._provenance_by_id(to_snapshot)

        added_ids = set(to_by_id) - set(from_by_id)
        removed_ids = set(from_by_id) - set(to_by_id)
        common_ids = set(from_by_id) & set(to_by_id)

        added = [self._item(cid, to_by_id[cid], to_provenance_by_id) for cid in sorted(added_ids)]
        removed = [self._item(cid, from_by_id[cid], from_provenance_by_id) for cid in sorted(removed_ids)]

        changed = []
        unchanged = []
        provenance_changes = []

        for context_id in sorted(common_ids):
            from_entry = from_by_id[context_id]
            to_entry = to_by_id[context_id]
            from_provenance = from_provenance_by_id.get(context_id)
            to_provenance = to_provenance_by_id.get(context_id)

            content_differs = from_entry.get("content") != to_entry.get("content")
            from_source_version = from_provenance.source_version if from_provenance is not None else None
            to_source_version = to_provenance.source_version if to_provenance is not None else None
            version_differs = from_source_version != to_source_version

            if content_differs or version_differs:
                changed.append(
                    {
                        "context_id": context_id,
                        "from_entry": from_entry,
                        "to_entry": to_entry,
                        "from_provenance": from_provenance,
                        "to_provenance": to_provenance,
                    }
                )
            else:
                unchanged.append(self._item(context_id, to_entry, to_provenance_by_id))

            if self._provenance_differs(from_provenance, to_provenance):
                provenance_changes.append(
                    {"context_id": context_id, "from_provenance": from_provenance, "to_provenance": to_provenance}
                )

        summary = {
            "from_version": from_snapshot.context_version,
            "to_version": to_snapshot.context_version,
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "provenance_changes": len(provenance_changes),
        }

        return TaskContextDiff(
            task_id=task_id,
            from_version=from_snapshot.context_version,
            to_version=to_snapshot.context_version,
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
            provenance_changes=provenance_changes,
            summary=summary,
        )

    # -- internals ------------------------------------------------------------

    def _resolve_snapshot(self, task_id: str, version):
        if isinstance(version, str):
            snapshot = self._snapshot_service.get(version)  # UnknownTaskContextSnapshotError propagates
            if snapshot.task_id != task_id:
                raise CrossTaskDiffError(
                    f"snapshot {version!r} belongs to task {snapshot.task_id!r}, not {task_id!r}"
                )
            return snapshot

        for snapshot in self._snapshot_service.list(task_id):
            if snapshot.context_version == version:
                return snapshot
        raise UnknownTaskContextVersionError(
            f"task {task_id!r} has no snapshot at context_version {version!r}"
        )

    @staticmethod
    def _entries_by_id(snapshot) -> dict:
        resolved_context = snapshot.resolved_context if isinstance(snapshot.resolved_context, dict) else {}
        return {
            entry["context_id"]: entry
            for entry in resolved_context.get("context", [])
            if isinstance(entry, dict) and entry.get("context_id")
        }

    @staticmethod
    def _provenance_by_id(snapshot) -> dict:
        by_id = {}
        for record in snapshot.provenance:
            by_id[record.context_id] = record  # last (most recent) wins
        return by_id

    @staticmethod
    def _item(context_id, entry, provenance_by_id) -> dict:
        return {
            "context_id": context_id,
            "entry": entry,
            "provenance": provenance_by_id.get(context_id),
        }

    @staticmethod
    def _provenance_differs(from_provenance, to_provenance) -> bool:
        if from_provenance is None and to_provenance is None:
            return False
        if from_provenance is None or to_provenance is None:
            return True
        return (
            from_provenance.source_type,
            from_provenance.source_id,
            from_provenance.source_version,
            from_provenance.excerpt,
        ) != (
            to_provenance.source_type,
            to_provenance.source_id,
            to_provenance.source_version,
            to_provenance.excerpt,
        )

    @staticmethod
    def _validate(task_id, from_version, to_version) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidTaskContextDiffError("task_id is required and must be a non-empty string")
        for label, version in (("from_version", from_version), ("to_version", to_version)):
            if isinstance(version, bool) or not isinstance(version, (int, str)):
                raise InvalidTaskContextDiffError(f"{label} must be an int (context_version) or a str (snapshot_id)")
            if isinstance(version, str) and not version:
                raise InvalidTaskContextDiffError(f"{label} must be a non-empty string when given as a snapshot_id")
