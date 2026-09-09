from datetime import datetime, timezone
from uuid import uuid4

from backend.agent_task_context_budgeting import BudgetedAgentTaskContext
from backend.agent_task_context_packaging import AgentContextPackage
from backend.agent_task_context_resolution import ResolvedAgentTaskContext
from backend.llm.context_provenance import LLMContextProvenance

from .in_memory_store import InMemoryProvenanceRecordStore
from .models import ContextProvenanceEntry, ContextProvenanceRecord, ContextProvenanceTrace, provenance_from_dict
from .store import ProvenanceRecordStore

# resolution_reasons carries this one synthetic, non-source-id key for
# Commit #2's own aggregate "task's own explicit context" note -- never a
# real context_id/memory_id, so it is excluded when discovering which
# sources to trace.
_TASK_CONTEXT_REASON_KEY = "__task_context__"


class InvalidProvenanceRecordError(ValueError):
    """Raised when record() is given malformed arguments, or a package/
    source that does not belong to task_id."""


class UnknownProvenanceRecordError(KeyError):
    """Raised when get()/trace() names a task_id with no recorded history at all."""


class UnknownProvenanceTraceError(KeyError):
    """Raised when trace() names a source_id never seen in any of
    task_id's recorded provenance history."""


class LLMAgentTaskContextProvenanceService:
    """Records and traces one task's context lineage across retrieval,
    selection, budgeting, and packaging.

    Not a parallel lineage/audit system: every fact this service records
    is read straight from what Commits #2-#4 of this series already
    computed -- backend.llm.context_provenance.LLMContextProvenance
    entries from Commit #4's own AgentContextPackage.provenance (the
    repository's existing provenance type, embedded verbatim), Commit
    #2's own resolution_reasons (why a source was included/excluded
    during retrieval/selection/memory), and Commit #3's own reasons (what
    budgeting did with it). record() never re-derives, re-scores, or
    re-decides anything -- it only reads and bundles.

    source (optional) lets a caller hand over whichever of Commit #2's
    ResolvedAgentTaskContext and Commit #3's BudgetedAgentTaskContext it
    still has on hand, as {"resolved": ..., "budgeted": ...} -- both
    keys optional (Rule: "record why context was included or excluded
    when the underlying service exposes that information" -- when a
    caller has neither, record() still succeeds with a thinner trail
    built from package.provenance and package.context/memories alone).

    Persistence is the same append-only-store pattern this series' own
    Commit #1 established (an InMemoryProvenanceRecordStore by default,
    or a JSON-file-backed store built on the same backend.storage.
    AtomicJsonFile) -- ProvenanceRecordStore itself has no update()/
    delete(), so a written record can never be altered through this
    service.

    record()/get()/trace() only ever read the package/source they are
    given and write one new, whole record to the store -- nothing here
    ever calls a task context, project context, memory, or policy
    service, and no context/memory source is ever touched, mutated, or
    re-persisted.
    """

    def __init__(self, store: ProvenanceRecordStore = None):
        self.store = store if store is not None else InMemoryProvenanceRecordStore()

    def record(self, task_id: str, package: AgentContextPackage, source: dict = None) -> ContextProvenanceRecord:
        """Record one immutable lineage snapshot for task_id from package
        (and, when given, source).

        Raises:
            InvalidProvenanceRecordError: If task_id is missing/blank,
                package is not an AgentContextPackage, package does not
                belong to task_id, source is given and is not a dict, or
                source["resolved"]/source["budgeted"] are given and do
                not belong to task_id
        """
        resolved, budgeted = self._validate(task_id, package, source)

        included_ids = self._included_ids(package)
        provenance_by_id = self._provenance_by_id(package)

        candidate_ids = set(provenance_by_id) | included_ids
        if resolved is not None:
            candidate_ids |= set(resolved.resolution_reasons) - {_TASK_CONTEXT_REASON_KEY}
        if budgeted is not None:
            candidate_ids |= set(budgeted.reasons)

        entries = tuple(
            self._entry_for(source_id, provenance_by_id, included_ids, resolved, budgeted)
            for source_id in sorted(candidate_ids)
        )

        record = ContextProvenanceRecord(
            record_id=str(uuid4()),
            task_id=task_id,
            entries=entries,
            created_at=datetime.now(timezone.utc),
        )
        return self.store.save(record)

    def get(self, task_id: str) -> list:
        """Every ContextProvenanceRecord ever recorded for task_id, oldest first."""
        return self.store.list_for_task(task_id)

    def trace(self, task_id: str, source_id: str) -> ContextProvenanceTrace:
        """source_id's current, complete lineage: the entry for it in the
        most recently recorded ContextProvenanceRecord for task_id that
        mentions it.

        Raises:
            UnknownProvenanceRecordError: If task_id has no recorded
                history at all
            UnknownProvenanceTraceError: If source_id was never seen in
                any of task_id's recorded history
        """
        records = self.store.list_for_task(task_id)
        if not records:
            raise UnknownProvenanceRecordError(task_id)

        for record in reversed(records):
            for entry in record.entries:
                if entry.source_id == source_id:
                    return ContextProvenanceTrace(
                        source=entry.source,
                        source_version=entry.source_version,
                        selection_reason=entry.selection_reason,
                        transformation=entry.transformation,
                        included=entry.included,
                        timestamp=record.created_at,
                    )

        raise UnknownProvenanceTraceError(f"no provenance trace for source {source_id!r} in task {task_id!r}")

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _included_ids(package: AgentContextPackage) -> set:
        context_ids = {
            message.get("metadata", {}).get("context_id")
            for message in package.context
            if isinstance(message, dict) and message.get("metadata", {}).get("context_id")
        }
        memory_ids = {
            memory.get("memory_id") for memory in package.memories if isinstance(memory, dict) and memory.get("memory_id")
        }
        return context_ids | memory_ids

    @staticmethod
    def _provenance_by_id(package: AgentContextPackage) -> dict:
        """package.provenance holds Commit #4's own plain-dict rendering
        of each LLMContextProvenance (AgentContextPackage's own documented
        shape) -- reconstructed back into the real repository type here so
        ContextProvenanceEntry.source stays an actual LLMContextProvenance,
        not a dict, per this commit's own "using existing repository
        types" instruction."""
        by_id = {}
        for entry in package.provenance:
            record = entry if isinstance(entry, LLMContextProvenance) else provenance_from_dict(entry)
            by_id[record.context_id] = record  # last (most recent) wins
        return by_id

    @staticmethod
    def _entry_for(source_id, provenance_by_id, included_ids, resolved, budgeted) -> ContextProvenanceEntry:
        provenance_record = provenance_by_id.get(source_id)
        return ContextProvenanceEntry(
            source_id=source_id,
            source=provenance_record,
            source_version=provenance_record.source_version if provenance_record is not None else None,
            selection_reason=resolved.resolution_reasons.get(source_id) if resolved is not None else None,
            transformation=budgeted.reasons.get(source_id) if budgeted is not None else None,
            included=source_id in included_ids,
        )

    @staticmethod
    def _validate(task_id, package, source):
        if not task_id or not isinstance(task_id, str):
            raise InvalidProvenanceRecordError("task_id is required and must be a non-empty string")
        if not isinstance(package, AgentContextPackage):
            raise InvalidProvenanceRecordError(
                f"package must be an AgentContextPackage, got {type(package).__name__}"
            )
        if package.task.get("task_id") != task_id:
            raise InvalidProvenanceRecordError(
                f"package belongs to task {package.task.get('task_id')!r}, not {task_id!r}"
            )

        if source is None:
            return None, None
        if not isinstance(source, dict):
            raise InvalidProvenanceRecordError("source must be a dict when given")

        resolved = source.get("resolved")
        if resolved is not None:
            if not isinstance(resolved, ResolvedAgentTaskContext):
                raise InvalidProvenanceRecordError("source['resolved'] must be a ResolvedAgentTaskContext")
            if resolved.task_id != task_id:
                raise InvalidProvenanceRecordError(
                    f"source['resolved'] belongs to task {resolved.task_id!r}, not {task_id!r}"
                )

        budgeted = source.get("budgeted")
        if budgeted is not None:
            if not isinstance(budgeted, BudgetedAgentTaskContext):
                raise InvalidProvenanceRecordError("source['budgeted'] must be a BudgetedAgentTaskContext")
            if budgeted.task_id != task_id:
                raise InvalidProvenanceRecordError(
                    f"source['budgeted'] belongs to task {budgeted.task_id!r}, not {task_id!r}"
                )

        return resolved, budgeted
