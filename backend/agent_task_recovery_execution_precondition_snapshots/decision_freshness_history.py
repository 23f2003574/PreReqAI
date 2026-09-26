from datetime import datetime, timezone

from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    FRESHNESS_FRESH,
    FRESHNESS_HISTORY_DECISION_RECORDED,
    FRESHNESS_HISTORY_FRESH_REUSE,
    FRESHNESS_HISTORY_INDETERMINATE_DETECTED,
    FRESHNESS_HISTORY_REVALIDATION_FAILED,
    FRESHNESS_HISTORY_REVALIDATION_REPLACED,
    FRESHNESS_HISTORY_REVALIDATION_REUSED,
    FRESHNESS_HISTORY_STALE_DETECTED,
    FRESHNESS_STALE,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessHistory,
    AgentTaskRecoveryExecutionDecisionFreshnessHistoryEvent,
    AgentTaskRecoveryExecutionDecisionFreshnessHistoryLink,
)

# At an identical timestamp a decision is listed before any audit record
# about it -- a decision must exist before it can be evaluated.
_DECISION_RANK = 0
_AUDIT_RANK = 1


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessHistoryError(ValueError):
    """Raised when get_history() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessHistoryService:
    """Makes freshness-driven decision replacement traceable as one
    chronological chain -- never another persistence system (Rule): the
    history is assembled on every call purely from the EXISTING decision
    store (Commit #7-of-the-earlier-series) and Commit #5's own freshness
    audit trail, both only ever read here.

    Never recomputes freshness or validation (Rule): every status, reason,
    state version, revalidation action and replacement id is copied
    verbatim from the persisted records -- no staleness/integrity/
    revalidation service is even a collaborator of this class.

    Never invents data for a missing or interrupted chain (Rule): a
    replacement the audit names but the store lacks, an audit about a
    decision the store never persisted, or a stale/indeterminate
    evaluation never followed by any recorded revalidation is reported in
    `gaps`, not filled in.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
    ):
        """
        Args:
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance the revalidation service persists
                through.
            freshness_audit_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService;
                pass the real instance holding the recorded evaluations.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._audit_service = (
            freshness_audit_service
            if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )

    def get_history(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionFreshnessHistory:
        """task_id's freshness history, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessHistoryError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessHistoryError(
                "task_id is required and must be a non-empty string"
            )

        decisions = self._decision_store.history(task_id)
        audits = self._audit_service.list(task_id)
        decisions_by_id = {decision.decision_id: decision for decision in decisions}

        entries = [
            ((decision.created_at, _DECISION_RANK, index, decision.decision_id), decision, None)
            for index, decision in enumerate(decisions)
        ] + [
            ((audit.recorded_at, _AUDIT_RANK, index, audit.audit_id), None, audit)
            for index, audit in enumerate(audits)
        ]
        entries.sort(key=lambda entry: entry[0])

        events = []
        for sequence, (_, decision, audit) in enumerate(entries, start=1):
            events.append(
                self._decision_event(sequence, decision)
                if decision is not None
                else self._audit_event(sequence, audit)
            )

        links = tuple(
            AgentTaskRecoveryExecutionDecisionFreshnessHistoryLink(
                old_decision_id=event.decision_id, new_decision_id=event.replacement_decision_id,
                audit_id=event.audit_id, linked_at=event.occurred_at,
                replacement_found=event.replacement_decision_id in decisions_by_id,
            )
            for event in events
            if event.event_type == FRESHNESS_HISTORY_REVALIDATION_REPLACED
        )

        audit_events = [event for event in events if event.audit_id is not None]
        original_decision_id = (
            decisions[0].decision_id if decisions
            else (audit_events[0].decision_id if audit_events else None)
        )

        gaps = self._gaps(audit_events, links, decisions_by_id)
        return AgentTaskRecoveryExecutionDecisionFreshnessHistory(
            task_id=task_id, events=tuple(events), links=links,
            original_decision_id=original_decision_id,
            current_decision_id=self._follow_chain(original_decision_id, links),
            fresh_reuse_count=sum(
                1 for event in audit_events if event.event_type == FRESHNESS_HISTORY_FRESH_REUSE
            ),
            revalidation_count=sum(1 for event in audit_events if event.revalidated),
            replacement_count=len(links),
            failed_revalidation_count=sum(
                1 for event in audit_events if event.event_type == FRESHNESS_HISTORY_REVALIDATION_FAILED
            ),
            gaps=gaps, complete=not gaps,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _decision_event(sequence, decision):
        return AgentTaskRecoveryExecutionDecisionFreshnessHistoryEvent(
            sequence=sequence, event_type=FRESHNESS_HISTORY_DECISION_RECORDED, occurred_at=decision.created_at,
            decision_id=decision.decision_id, freshness_status=None, freshness_reason=None,
            decision_state_version=None, current_state_version=None, revalidated=False,
            revalidation_action=None, replacement_decision_id=None, execution_decision=decision.decision,
            audit_id=None,
        )

    @staticmethod
    def _audit_event(sequence, audit):
        if audit.revalidated:
            if audit.revalidation_action == REVALIDATION_FAILED:
                event_type = FRESHNESS_HISTORY_REVALIDATION_FAILED
            elif audit.revalidation_action == REVALIDATION_REPLACED and audit.replacement_decision_id:
                event_type = FRESHNESS_HISTORY_REVALIDATION_REPLACED
            else:
                event_type = FRESHNESS_HISTORY_REVALIDATION_REUSED
        elif audit.freshness_status == FRESHNESS_FRESH:
            event_type = FRESHNESS_HISTORY_FRESH_REUSE
        elif audit.freshness_status == FRESHNESS_STALE:
            event_type = FRESHNESS_HISTORY_STALE_DETECTED
        else:
            event_type = FRESHNESS_HISTORY_INDETERMINATE_DETECTED
        return AgentTaskRecoveryExecutionDecisionFreshnessHistoryEvent(
            sequence=sequence, event_type=event_type, occurred_at=audit.recorded_at,
            decision_id=audit.decision_id, freshness_status=audit.freshness_status,
            freshness_reason=audit.freshness_reason, decision_state_version=audit.decision_state_version,
            current_state_version=audit.current_state_version, revalidated=audit.revalidated,
            revalidation_action=audit.revalidation_action,
            replacement_decision_id=audit.replacement_decision_id, execution_decision=None,
            audit_id=audit.audit_id,
        )

    @staticmethod
    def _follow_chain(start_decision_id, links):
        current = start_decision_id
        seen = {current}
        for link in links:
            if link.old_decision_id == current and link.new_decision_id not in seen:
                current = link.new_decision_id
                seen.add(current)
        return current

    @staticmethod
    def _gaps(audit_events, links, decisions_by_id) -> tuple:
        gaps = []
        for event in audit_events:
            if event.decision_id not in decisions_by_id:
                gaps.append(
                    f"audit {event.audit_id} evaluates decision {event.decision_id}, "
                    "which the decision store does not hold"
                )
        for link in links:
            if not link.replacement_found:
                gaps.append(
                    f"audit {link.audit_id} names replacement decision {link.new_decision_id} "
                    f"for {link.old_decision_id}, which the decision store does not hold"
                )
        # A stale/indeterminate evaluation is only an interrupted chain
        # when NO later audit for that same decision records a revalidation.
        for index, event in enumerate(audit_events):
            if event.event_type not in (
                FRESHNESS_HISTORY_STALE_DETECTED, FRESHNESS_HISTORY_INDETERMINATE_DETECTED
            ):
                continue
            if not any(
                later.decision_id == event.decision_id and later.revalidated
                for later in audit_events[index + 1:]
            ):
                gaps.append(
                    f"decision {event.decision_id} was evaluated {event.freshness_status} "
                    f"(audit {event.audit_id}) but no revalidation was recorded afterwards"
                )
        return tuple(gaps)
