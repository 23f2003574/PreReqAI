from datetime import datetime, timezone

from .decision_supersession_conflict import LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .models import (
    POINTER_STATUS_AGREES,
    POINTER_STATUS_DISAGREES,
    POINTER_STATUS_UNSET,
    POINTER_STATUS_UNVERIFIABLE,
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictReport,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictReportError(ValueError):
    """Raised when report() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictReportingService:
    """A task-level operational report of decision-lineage conflicts,
    following the existing decision reporting service's pattern: it calls
    the conflict detector (#4) once and the supersession resolution (#3)
    once, and only reshapes their already-computed results -- never
    rediscovering a conflict, resolving one, or writing anything.
    Conflict evidence and order are the detector's own; a conflict-free or
    empty task still yields a complete report.
    """

    def __init__(
        self,
        conflict_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService = None,
        resolution_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService = None,
    ):
        """Pass a conflict_service and resolution_service wired to the same
        stores; by default the resolution service is the one the default
        conflict service itself uses."""
        if conflict_service is None:
            resolution_service = (
                resolution_service if resolution_service is not None
                else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService()
            )
            conflict_service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
                resolution_service=resolution_service
            )
        self._conflict_service = conflict_service
        self._resolution_service = (
            resolution_service if resolution_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService()
        )

    def report(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictReport:
        """task_id's lineage-conflict report.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictReportError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictReportError(
                "task_id is required and must be a non-empty string"
            )

        detection = self._conflict_service.detect(task_id)
        resolution = self._resolution_service.resolve(task_id)

        conflict_types, counts = [], {}
        for conflict in detection.conflicts:
            if conflict.conflict_type not in counts:
                conflict_types.append(conflict.conflict_type)
            counts[conflict.conflict_type] = counts.get(conflict.conflict_type, 0) + 1

        if resolution.reconciled_pointer is None:
            pointer_status = POINTER_STATUS_UNSET
        elif resolution.resolution_state == RESOLUTION_RESOLVED:
            pointer_status = POINTER_STATUS_AGREES
        elif resolution.resolution_state == RESOLUTION_CONFLICT:
            pointer_status = POINTER_STATUS_DISAGREES
        else:
            pointer_status = POINTER_STATUS_UNVERIFIABLE

        return AgentTaskRecoveryExecutionDecisionSupersessionConflictReport(
            task_id=task_id, conflict_count=len(detection.conflicts),
            affected_decision_ids=detection.affected_decision_ids, conflict_types=tuple(conflict_types),
            counts_by_type=counts, severity=detection.severity, pointer_status=pointer_status,
            reconciled_pointer=resolution.reconciled_pointer,
            terminal_decision_id=resolution.terminal_decision_id,
            resolution_state=resolution.resolution_state,
            chain_validation_status="invalid" if resolution.resolution_state == RESOLUTION_REJECTED else "valid",
            unresolved_conflicts=detection.conflicts, generated_at=datetime.now(timezone.utc),
        )
