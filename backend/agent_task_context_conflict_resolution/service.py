from backend.agent_task_context import LLMAgentTaskContextService

from .models import ContextConflictResolutionResult


class InvalidConflictResolutionError(ValueError):
    """Raised when resolve() is given a missing/blank task_id, or
    conflicts that is not a list."""


class LLMAgentTaskContextConflictResolver:
    """Deterministically adjudicates the conflicts Commit #8's own
    LLMAgentTaskContextReconciler already found for one task, without
    touching stored context.

    Not a second resolution engine: resolve() never re-runs retrieval,
    authorization, or freshness itself -- it trusts and adjudicates
    exactly what Commit #8 already computed and handed over as
    `conflicts` (entries shaped like that Result's own `changed` --
    {"context_id", "stored_entry", "fresh_entry", "stored_provenance",
    "fresh_provenance"} -- a genuine two-sided version conflict -- or its
    own `conflicts` -- {"context_id", "reason", "entry", "provenance"} --
    a one-sided authorization violation, both accepted here verbatim).
    Precedence reuses two existing, already-established signals rather
    than inventing a priority scheme: backend.llm.context_compaction's
    own metadata["priority"] == "high" marker (the same one Commit #3's
    budgeter already reuses to protect the task's own explicit context
    from compaction) settles a two-sided conflict when exactly one side
    carries it; failing that, the fresh side wins by definition (Commit
    #8 only ever puts a source in `changed` after reading its *current*
    live content, so "fresh" already means "verified current" -- no
    second freshness check is run here). An authority violation
    ("denied" already present in Commit #8's own reason text) always
    discards its source outright -- the same "explicit deny always wins"
    convention every policy consumer in this repository already applies.

    Rule "explicit task constraints must not be overridden by
    supplemental context" is satisfied structurally: resolve() never
    reads or writes LLMAgentTaskContext.constraints (or .inputs) at all --
    it only ever adjudicates the context sources it is handed.

    A conflict is left in unresolved_conflicts, untouched, whenever no
    real signal settles it: both sides claim metadata["priority"] ==
    "high" (a genuine, unresolvable contradiction), a version conflict
    has no fresh_entry to prefer against, an authorization conflict's
    reason does not actually name a denial, or an entry names a
    scope_id other than task_id's own (Rule: "respect existing scope...
    semantics" -- cross-scope data is never silently adjudicated).

    resolve() only ever reads task_context_service.get(task_id) (to
    confirm task_id exists and to learn its scope_id) and the conflicts
    list it is given -- it never calls update()/snapshot() on the task
    context, and never touches a project context, memory, or policy
    store. Rule "feed the result back through existing integrity
    validation before packaging" is a caller-workflow instruction, not
    an internal call this service makes itself: a caller is expected to
    run Commit #5's own LLMAgentTaskContextIntegrityService.validate()
    against whatever AgentContextPackage is eventually built from
    `resolved`, before that package is actually used.
    """

    def __init__(self, task_context_service: LLMAgentTaskContextService):
        self._task_context_service = task_context_service

    def resolve(self, task_id: str, conflicts: list) -> ContextConflictResolutionResult:
        """Adjudicate conflicts for task_id.

        Raises:
            InvalidConflictResolutionError: If task_id is missing/blank,
                or conflicts is not a list
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
        """
        self._validate(task_id, conflicts)
        task_context = self._task_context_service.get(task_id)

        resolved = []
        decisions = []
        discarded = []
        unresolved = []
        reasons = {}

        for conflict in conflicts:
            context_id = conflict.get("context_id") if isinstance(conflict, dict) else None
            if not isinstance(conflict, dict) or not context_id:
                unresolved.append(conflict)
                continue

            mismatched_scope = self._scope_mismatch(conflict, task_context.scope_id)
            if mismatched_scope is not None:
                unresolved.append(conflict)
                reasons[context_id] = (
                    f"context {context_id!r} names scope {mismatched_scope!r}, not task {task_id!r}'s own "
                    f"scope {task_context.scope_id!r} -- left unresolved"
                )
                continue

            if "stored_entry" in conflict or "fresh_entry" in conflict:
                outcome = self._resolve_version_conflict(conflict)
            elif "reason" in conflict:
                outcome = self._resolve_authority_conflict(conflict)
            else:
                outcome = None

            if outcome is None:
                unresolved.append(conflict)
                reasons[context_id] = f"context {context_id!r}: no deterministic signal to resolve this conflict"
                continue

            decisions.append(
                {"context_id": context_id, "decision": outcome["decision"], "reason": outcome["reason"]}
            )
            reasons[context_id] = outcome["reason"]
            if outcome["winner"] is not None:
                resolved.append(outcome["winner"])
            if outcome["loser"] is not None:
                discarded.append(outcome["loser"])

        return ContextConflictResolutionResult(
            task_id=task_id,
            resolved=resolved,
            decisions=decisions,
            discarded_sources=discarded,
            unresolved_conflicts=unresolved,
            reasons=reasons,
        )

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _scope_mismatch(conflict: dict, scope_id: str):
        for key in ("entry", "stored_entry", "fresh_entry"):
            entry = conflict.get(key)
            if isinstance(entry, dict) and entry.get("scope_id") and entry["scope_id"] != scope_id:
                return entry["scope_id"]
        return None

    @staticmethod
    def _is_high_priority(entry) -> bool:
        if not isinstance(entry, dict):
            return False
        metadata = entry.get("metadata") or {}
        return metadata.get("priority") == "high"

    def _resolve_version_conflict(self, conflict: dict):
        context_id = conflict["context_id"]
        stored_entry = conflict.get("stored_entry")
        fresh_entry = conflict.get("fresh_entry")
        stored_provenance = conflict.get("stored_provenance")
        fresh_provenance = conflict.get("fresh_provenance")

        stored_high = self._is_high_priority(stored_entry)
        fresh_high = self._is_high_priority(fresh_entry)

        if stored_high and fresh_high:
            return None  # both sides claim highest priority -- a genuine contradiction

        if stored_high:
            winner = {"context_id": context_id, "entry": stored_entry, "provenance": stored_provenance}
            loser = (
                {"context_id": context_id, "entry": fresh_entry, "provenance": fresh_provenance}
                if fresh_entry is not None
                else None
            )
            return {
                "decision": "kept_stored",
                "reason": f"context {context_id!r}: stored source is marked priority=high, kept over the fresh source",
                "winner": winner,
                "loser": loser,
            }

        if fresh_entry is not None:
            winner = {"context_id": context_id, "entry": fresh_entry, "provenance": fresh_provenance}
            loser = (
                {"context_id": context_id, "entry": stored_entry, "provenance": stored_provenance}
                if stored_entry is not None
                else None
            )
            return {
                "decision": "kept_fresh",
                "reason": f"context {context_id!r}: fresh source is verified current, preferred over the stored source",
                "winner": winner,
                "loser": loser,
            }

        return None  # no fresh_entry to prefer against -- nothing deterministic to decide

    @staticmethod
    def _resolve_authority_conflict(conflict: dict):
        context_id = conflict["context_id"]
        reason_text = conflict.get("reason") or ""
        if "denied" not in reason_text:
            return None  # does not actually name an authorization violation

        return {
            "decision": "discarded_unauthorized",
            "reason": f"context {context_id!r}: discarded -- {reason_text}",
            "winner": None,
            "loser": {"context_id": context_id, "entry": conflict.get("entry"), "provenance": conflict.get("provenance")},
        }

    @staticmethod
    def _validate(task_id, conflicts) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidConflictResolutionError("task_id is required and must be a non-empty string")
        if not isinstance(conflicts, list):
            raise InvalidConflictResolutionError("conflicts must be a list")
