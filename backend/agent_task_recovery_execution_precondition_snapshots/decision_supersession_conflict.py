from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_repair import InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession import InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .models import (
    CONFLICT_SEVERITIES,
    CONFLICT_SEVERITY_CRITICAL,
    CONFLICT_SEVERITY_HIGH,
    CONFLICT_SEVERITY_MEDIUM,
    CONFLICT_SEVERITY_NONE,
    RESOLUTION_CONFLICT,
    SUPERSESSION_CONFLICT_CROSS_TASK,
    SUPERSESSION_CONFLICT_CYCLE,
    SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT,
    SUPERSESSION_CONFLICT_INVALID_REASON,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER,
    SUPERSESSION_CONFLICT_TYPES,
    AgentTaskRecoveryExecutionDecisionSupersessionConflict,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResult,
)

_SEVERITY = {
    SUPERSESSION_CONFLICT_CYCLE: CONFLICT_SEVERITY_CRITICAL,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS: CONFLICT_SEVERITY_CRITICAL,
    SUPERSESSION_CONFLICT_CROSS_TASK: CONFLICT_SEVERITY_CRITICAL,
    SUPERSESSION_CONFLICT_MISSING_DECISION: CONFLICT_SEVERITY_CRITICAL,
    SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER: CONFLICT_SEVERITY_HIGH,
    SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT: CONFLICT_SEVERITY_HIGH,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT: CONFLICT_SEVERITY_HIGH,
    SUPERSESSION_CONFLICT_INVALID_REASON: CONFLICT_SEVERITY_MEDIUM,
}


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictError(ValueError):
    """Raised when detect() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService:
    """Detects conflicting decision-lineage conditions before they can
    reach execution -- detection only: it never repairs, never picks a
    winner between conflicting records, and never writes anything
    (authorization and execution state are not even collaborators).

    Chain validation and terminal resolution are delegated to the
    supersession resolution service (#3, itself built on #2's validation);
    this class adds only a structured, typed view of the individual
    conflicting records -- every supersession_id/audit_id involved is kept
    as evidence -- in a deterministic order (conflict type, then decision
    ids, then evidence ids).
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_store=None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store=None,
        resolution_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService = None,
    ):
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._supersession_store = (
            supersession_store if supersession_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        )
        self._audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        self._resolution_service = (
            resolution_service if resolution_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
                decision_store=self._decision_store, supersession_store=self._supersession_store,
                freshness_audit_service=self._audit_service, chain_index_store=index_store,
            )
        )

    def detect(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictResult:
        """Detect task_id's lineage conflicts.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictError(
                "task_id is required and must be a non-empty string"
            )

        records = self._supersession_store.list_for_task(task_id)
        conflicts = []

        def add(conflict_type, decision_ids, evidence_ids, detail):
            conflicts.append(
                AgentTaskRecoveryExecutionDecisionSupersessionConflict(
                    conflict_type=conflict_type, severity=_SEVERITY[conflict_type],
                    decision_ids=tuple(decision_ids), evidence_ids=tuple(sorted(evidence_ids)), detail=detail,
                )
            )

        successors = {}
        for record in records:
            successors.setdefault(record.previous_decision_id, {}).setdefault(
                record.replacement_decision_id, []
            ).append(record.supersession_id)
            label = f"supersession {record.previous_decision_id} -> {record.replacement_decision_id}"
            if not isinstance(record.reason, str) or not record.reason.strip():
                add(SUPERSESSION_CONFLICT_INVALID_REASON,
                    (record.previous_decision_id, record.replacement_decision_id), (record.supersession_id,),
                    f"{label} has no valid supersession reason")
            previous = self._decision_store.get(record.previous_decision_id)
            replacement = self._decision_store.get(record.replacement_decision_id)
            for role, decision_id, decision in (
                ("previous", record.previous_decision_id, previous),
                ("replacement", record.replacement_decision_id, replacement),
            ):
                if decision is None:
                    add(SUPERSESSION_CONFLICT_MISSING_DECISION, (decision_id,), (record.supersession_id,),
                        f"{label}: {role} decision {decision_id} does not exist")
                elif decision.task_id != task_id or record.task_id != task_id:
                    add(SUPERSESSION_CONFLICT_CROSS_TASK, (decision_id,), (record.supersession_id,),
                        f"{label}: {role} decision {decision_id} belongs to task {decision.task_id!r}, "
                        f"not {task_id!r}")
            if previous is not None and replacement is not None and replacement.created_at <= previous.created_at:
                add(SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER,
                    (record.previous_decision_id, record.replacement_decision_id), (record.supersession_id,),
                    f"{label}: the replacement is not newer than the decision it supersedes")

        for previous_id, targets in successors.items():
            if len(targets) > 1:
                add(SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS, (previous_id, *sorted(targets)),
                    [evidence for ids in targets.values() for evidence in ids],
                    f"decision {previous_id} has multiple successors: {', '.join(sorted(targets))}")

        for cycle in self._cycles({old: set(targets) for old, targets in successors.items()}):
            evidence = [
                supersession_id
                for old, new in zip(cycle, cycle[1:] + cycle[:1])
                for supersession_id in successors.get(old, {}).get(new, [])
            ]
            add(SUPERSESSION_CONFLICT_CYCLE, cycle, evidence,
                f"supersession cycle: {' -> '.join(cycle + (cycle[0],))}")

        for audit in self._audit_service.list(task_id):
            if audit.replacement_decision_id is None:
                continue
            recorded = successors.get(audit.decision_id, {})
            for other in sorted(recorded):
                if other != audit.replacement_decision_id:
                    add(SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT,
                        (audit.decision_id, other, audit.replacement_decision_id),
                        [audit.audit_id, *recorded[other]],
                        f"supersession {audit.decision_id} -> {other} disagrees with freshness revalidation "
                        f"{audit.decision_id} -> {audit.replacement_decision_id}")

        resolution = self._resolution_service.resolve(task_id)
        if resolution.resolution_state == RESOLUTION_CONFLICT:
            terminal = resolution.chain[-1] if resolution.chain else None
            add(SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
                tuple(d for d in (terminal, resolution.reconciled_pointer) if d is not None), (),
                resolution.issues[0])

        type_rank = {conflict_type: rank for rank, conflict_type in enumerate(SUPERSESSION_CONFLICT_TYPES)}
        unique = {}
        for conflict in conflicts:
            unique.setdefault(
                (conflict.conflict_type, conflict.decision_ids, conflict.evidence_ids, conflict.detail), conflict
            )
        ordered = sorted(
            unique.values(),
            key=lambda c: (type_rank[c.conflict_type], c.decision_ids, c.evidence_ids, c.detail),
        )
        severity = max(
            (conflict.severity for conflict in ordered), key=CONFLICT_SEVERITIES.index,
            default=CONFLICT_SEVERITY_NONE,
        )
        return AgentTaskRecoveryExecutionDecisionSupersessionConflictResult(
            task_id=task_id, has_conflicts=bool(ordered), conflicts=tuple(ordered),
            affected_decision_ids=tuple(sorted({d for c in ordered for d in c.decision_ids})),
            severity=severity, resolution_state=resolution.resolution_state,
        )

    @staticmethod
    def _cycles(graph):
        """Every distinct simple cycle, each starting at its smallest id."""
        found = []

        def walk(start, node, path):
            for nxt in sorted(graph.get(node, ())):
                if nxt == start:
                    found.append(tuple(path))
                elif nxt > start and nxt not in path:
                    walk(start, nxt, path + [nxt])

        for start in sorted(graph):
            walk(start, start, [start])
        return sorted(set(found))
