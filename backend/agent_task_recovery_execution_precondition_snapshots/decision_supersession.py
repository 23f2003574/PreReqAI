from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_repair import (
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
)
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionError(ValueError):
    """Raised when supersede() is given invalid, missing, cross-task,
    non-newer, cyclic or conflicting decisions."""


class AgentTaskRecoveryExecutionDecisionSupersessionStore(ABC):
    """Raw, append-only persistence for supersession records -- the same
    dual-index (supersession_id, task_id) shape as the other stores in
    this package. There is no update()/delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryExecutionDecisionSupersessionRecord
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionRecord:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore(AgentTaskRecoveryExecutionDecisionSupersessionStore):
    """Stores supersession records in memory, for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_task: dict = {}

    def save(
        self, record: AgentTaskRecoveryExecutionDecisionSupersessionRecord
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionRecord:
        stored = deepcopy(record)
        self._by_id[record.supersession_id] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        return [deepcopy(entry) for entry in self._by_task.get(task_id, [])]


class LLMAgentTaskRecoveryExecutionDecisionSupersessionService:
    """Makes decision replacement explicit: records old -> new decision
    lineage so the currently authoritative decision can be told apart from
    decisions superseded by freshness revalidation -- explicit lineage,
    not another decision store: decisions are only ever read from the
    existing decision store and never modified.

    Shares one linkage with freshness revalidation/reconciliation:
    conflicts and cycles are checked against the freshness audit trail's
    own replacement links as well as recorded supersessions, and every
    new supersession is also written as a link into Commit #8's chain
    index, which chain validation (#7) and reconciliation (#9) already
    read -- so a supersession and a freshness replacement are the same
    link to them.

    A supersession never changes either decision's verdict: a review or
    block decision stays review/block; only the replacement's own
    persisted verdict is ever current.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        store: AgentTaskRecoveryExecutionDecisionSupersessionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store: AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore = None,
    ):
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self._audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        self._index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )

    def supersede(
        self, task_id: str, previous_decision_id: str, replacement_decision_id: str, reason: str
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionRecord:
        """Record that replacement_decision_id supersedes
        previous_decision_id for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionError:
                If any argument is not a non-empty string, either decision
                does not exist or belongs to another task, the replacement
                is not newer, or the link would create a cycle or conflict
                with an existing replacement
        """
        for value, name in (
            (task_id, "task_id"), (previous_decision_id, "previous_decision_id"),
            (replacement_decision_id, "replacement_decision_id"), (reason, "reason"),
        ):
            self._require_text(value, name)
        if previous_decision_id == replacement_decision_id:
            self._fail(f"decision {previous_decision_id} cannot supersede itself")

        previous = self._decision_store.get(previous_decision_id)
        replacement = self._decision_store.get(replacement_decision_id)
        for label, decision_id, decision in (
            ("previous", previous_decision_id, previous), ("replacement", replacement_decision_id, replacement),
        ):
            if decision is None:
                self._fail(f"{label} decision {decision_id} does not exist")
            if decision.task_id != task_id:
                self._fail(f"{label} decision {decision_id} belongs to task {decision.task_id!r}, not {task_id!r}")

        for existing in self._store.list_for_task(task_id):
            if (existing.previous_decision_id, existing.replacement_decision_id) == (
                previous_decision_id, replacement_decision_id,
            ):
                return existing

        if replacement.created_at <= previous.created_at:
            self._fail(
                f"replacement decision {replacement_decision_id} is not newer than {previous_decision_id}"
            )

        links = self._links(task_id)
        successors = dict(links)
        predecessors = {new: old for old, new in links}
        if previous_decision_id in successors and successors[previous_decision_id] != replacement_decision_id:
            self._fail(
                f"decision {previous_decision_id} is already superseded by {successors[previous_decision_id]}"
            )
        if replacement_decision_id in predecessors and predecessors[replacement_decision_id] != previous_decision_id:
            self._fail(
                f"decision {replacement_decision_id} already supersedes {predecessors[replacement_decision_id]}"
            )
        cursor, seen = replacement_decision_id, set()
        while cursor in successors and cursor not in seen:
            seen.add(cursor)
            cursor = successors[cursor]
            if cursor == previous_decision_id:
                self._fail(
                    f"superseding {previous_decision_id} with {replacement_decision_id} would create a cycle"
                )

        record = self._store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=task_id, previous_decision_id=previous_decision_id,
                replacement_decision_id=replacement_decision_id, previous_decision=previous.decision,
                replacement_decision=replacement.decision, reason=reason, recorded_at=datetime.now(timezone.utc),
            )
        )
        self._link_into_chain_index(task_id, previous_decision_id, replacement_decision_id)
        return record

    def get_current(self, task_id: str) -> Optional[str]:
        """The currently authoritative decision_id: the end of the
        supersession lineage starting at task_id's earliest decision. None
        (fail closed) when no decision exists, or the lineage does not end
        at the newest persisted decision (an unlinked newer decision makes
        it ambiguous)."""
        self._require_text(task_id, "task_id")
        decisions = self._decision_store.history(task_id)
        if not decisions:
            return None
        successors = dict(self._links(task_id))
        cursor, seen = decisions[0].decision_id, set()
        while cursor in successors and cursor not in seen:
            seen.add(cursor)
            cursor = successors[cursor]
        return cursor if cursor == decisions[-1].decision_id else None

    def get_supersession_chain(self, task_id: str) -> list:
        """task_id's explicit supersession records in lineage order (each
        chain from its root decision), then by recording time."""
        self._require_text(task_id, "task_id")
        records = self._store.list_for_task(task_id)
        by_previous = {record.previous_decision_id: record for record in records}
        replaced = {record.replacement_decision_id for record in records}
        ordered = []
        for root in sorted(
            (record for record in records if record.previous_decision_id not in replaced),
            key=lambda record: record.recorded_at,
        ):
            cursor = root
            while cursor is not None and cursor not in ordered:
                ordered.append(cursor)
                cursor = by_previous.get(cursor.replacement_decision_id)
        return ordered

    def _links(self, task_id):
        links = [
            (record.previous_decision_id, record.replacement_decision_id)
            for record in self._store.list_for_task(task_id)
        ]
        for audit in self._audit_service.list(task_id):
            if audit.replacement_decision_id is not None:
                link = (audit.decision_id, audit.replacement_decision_id)
                if link not in links:
                    links.append(link)
        return links

    def _link_into_chain_index(self, task_id, previous_decision_id, replacement_decision_id):
        audit_links = {
            (audit.decision_id, audit.replacement_decision_id) for audit in self._audit_service.list(task_id)
        }
        link = (previous_decision_id, replacement_decision_id)
        index = self._index_store.get(task_id)
        existing = index.links if index is not None else ()
        if link in audit_links or link in existing:
            return
        self._index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=task_id, links=existing + (link,),
                current_decision_id=index.current_decision_id if index is not None else None,
                updated_at=datetime.now(timezone.utc),
            )
        )

    @staticmethod
    def _fail(message):
        raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionError(message)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionError(
                f"{field_name} is required and must be a non-empty string"
            )
