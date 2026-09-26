from datetime import datetime, timezone

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    CHAIN_INVALID,
    CHAIN_VALID,
    FRESHNESS_FRESH,
    INTEGRITY_VALID,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainValidationError(ValueError):
    """Raised when validate() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService:
    """The integrity boundary for freshness-driven decision replacement:
    verifies that every stale decision was replaced by a valid, newer
    successor and that the old -> new chain the freshness audit trail
    records agrees with the decision store -- never another persistence
    or audit framework (Rule): both the decision store and Commit #5's own
    audit trail are only ever read here, and no decision, freshness or
    revalidation result is recomputed.

    Fails closed (Rule): any broken, cyclic, duplicated or contradictory
    link, or any disagreement between the chain's terminal point and the
    store's own latest decision, makes the result CHAIN_INVALID with
    latest_decision_id None -- a current decision is never guessed.

    `integrity_service` (Commit #1's own
    LLMAgentTaskRecoveryExecutionDecisionIntegrityService) is optional:
    when given, each decision on the chain must also pass its check().
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        integrity_service=None,
        chain_index_store=None,
    ):
        """
        Args:
            chain_index_store: Optional
                AgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
                whose derived links (written only by the chain repair
                service) supplement the audit trail's own linkage.
        """
        self._chain_index_store = chain_index_store
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._audit_service = (
            freshness_audit_service
            if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        self._integrity_service = integrity_service

    def validate(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult:
        """Validate task_id's freshness replacement chain.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainValidationError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainValidationError(
                "task_id is required and must be a non-empty string"
            )

        decisions = self._decision_store.history(task_id)
        audits = self._audit_service.list(task_id)
        issues = []

        if not decisions:
            issues.append("no decisions are recorded for this task; the current chain cannot be established")
            for audit in audits:
                issues.append(f"audit {audit.audit_id} references decision {audit.decision_id}, which does not exist")
            return self._result(task_id, issues, ())

        by_id = {}
        for decision in decisions:
            if decision.decision_id in by_id:
                issues.append(f"decision {decision.decision_id} is recorded more than once")
                continue
            by_id[decision.decision_id] = decision
            if decision.task_id != task_id:
                issues.append(f"decision {decision.decision_id} belongs to task {decision.task_id!r}, not {task_id!r}")
            if not decision.snapshot_id:
                issues.append(f"decision {decision.decision_id} has no snapshot reference")
            if not decision.authorization_id:
                issues.append(f"decision {decision.decision_id} has no authorization reference")

        successors, predecessors, seen_links = {}, {}, set()
        unnamed_replacements = []

        def add_link(old_id, new_id, source):
            if new_id == old_id:
                issues.append(f"{source} links decision {old_id} to itself")
                return
            if old_id in successors:
                issues.append(
                    f"decision {old_id} is replaced by both {successors[old_id]} and {new_id} (contradictory links)"
                )
                return
            if new_id in predecessors:
                issues.append(
                    f"decision {new_id} replaces both {predecessors[new_id]} and {old_id} (contradictory links)"
                )
                return
            successors[old_id] = new_id
            predecessors[new_id] = old_id
            new = by_id.get(new_id)
            old = by_id.get(old_id)
            if new is None:
                issues.append(f"replacement decision {new_id} (for {old_id}) does not exist")
            elif old is not None and new.created_at <= old.created_at:
                issues.append(f"replacement decision {new_id} is not newer than the decision {old_id} it replaces")

        for audit in audits:
            if audit.task_id != task_id:
                issues.append(f"audit {audit.audit_id} belongs to task {audit.task_id!r}, not {task_id!r}")
            if audit.decision_id not in by_id:
                issues.append(f"audit {audit.audit_id} references decision {audit.decision_id}, which does not exist")
            new_id = audit.replacement_decision_id
            if new_id is None:
                if audit.revalidation_action == REVALIDATION_REPLACED:
                    unnamed_replacements.append(audit)
                continue
            old_id = audit.decision_id
            if audit.revalidation_action != REVALIDATION_REPLACED:
                issues.append(
                    f"audit {audit.audit_id} names replacement {new_id} but its revalidation action is "
                    f"{audit.revalidation_action!r}, not {REVALIDATION_REPLACED!r}"
                )
            if audit.freshness_status == FRESHNESS_FRESH:
                issues.append(f"audit {audit.audit_id} replaces decision {old_id} even though it was evaluated fresh")
            if (old_id, new_id) in seen_links:
                issues.append(f"link {old_id} -> {new_id} is recorded more than once")
                continue
            seen_links.add((old_id, new_id))
            add_link(old_id, new_id, f"audit {audit.audit_id}")

        # Derived (non-authoritative) links from the chain index -- only
        # ever ADD linkage the audit trail itself lacks; a link the audit
        # trail already records, or a repeated derived link, is ignored.
        index = self._chain_index_store.get(task_id) if self._chain_index_store is not None else None
        for old_id, new_id in (index.links if index is not None else ()):
            if (old_id, new_id) in seen_links:
                continue
            seen_links.add((old_id, new_id))
            if old_id not in by_id:
                issues.append(f"derived link {old_id} -> {new_id} references decision {old_id}, which does not exist")
                continue
            add_link(old_id, new_id, "derived link")

        # A REPLACED audit that lost its replacement id is only an issue
        # while no derived link supplies that decision's successor.
        for audit in unnamed_replacements:
            if audit.decision_id not in successors:
                issues.append(f"audit {audit.audit_id} records a replacement but names no replacement decision")

        chain = [decisions[0].decision_id]
        while chain[-1] in successors:
            nxt = successors[chain[-1]]
            if nxt in chain:
                issues.append(f"replacement chain is cyclic: {' -> '.join(chain + [nxt])}")
                break
            chain.append(nxt)
        terminal = chain[-1]

        for decision_id in by_id:
            if decision_id not in chain:
                issues.append(
                    f"decision {decision_id} is not linked into the replacement chain (missing audit evidence)"
                )

        latest = decisions[-1].decision_id
        if terminal != latest:
            issues.append(f"the latest decision {latest} is not the chain's terminal point {terminal}")

        terminal_audits = [audit for audit in audits if audit.decision_id == terminal]
        if terminal_audits and terminal_audits[-1].freshness_status != FRESHNESS_FRESH:
            last = terminal_audits[-1]
            issues.append(
                f"terminal decision {terminal} was last evaluated {last.freshness_status} "
                f"(audit {last.audit_id}) and never replaced, yet would be presented as current"
            )

        if self._integrity_service is not None:
            for decision_id in chain:
                if decision_id not in by_id:
                    continue
                integrity = self._integrity_service.check(task_id, decision_id)
                if integrity.status != INTEGRITY_VALID:
                    issues.append(
                        f"decision {decision_id} failed its integrity check: {'; '.join(integrity.issues)}"
                    )

        return self._result(task_id, issues, tuple(chain))

    @staticmethod
    def _result(task_id, issues, chain):
        status = CHAIN_INVALID if issues else CHAIN_VALID
        return AgentTaskRecoveryExecutionDecisionFreshnessChainValidationResult(
            task_id=task_id, status=status, issues=tuple(issues), chain=chain,
            latest_decision_id=chain[-1] if status == CHAIN_VALID else None,
            validated_at=datetime.now(timezone.utc),
        )
