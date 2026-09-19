from datetime import datetime
from typing import Optional

from .cleanup import EXPIRED_REASON, INVALIDATED_REASON
from .cleanup_candidates import (
    AgentTaskRecoveryScheduleCleanupCandidate,
    LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService,
)


class InvalidAgentTaskRecoveryScheduleCleanupOrderingError(ValueError):
    """Raised when order() is given invalid arguments."""


# Invalidated first: its authorization no longer validates, so it is the
# more urgent one to make terminal; merely-overdue (expired) follows.
_REASON_PRECEDENCE = {INVALIDATED_REASON: 0, EXPIRED_REASON: 1}


class LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService:
    """Puts cleanup candidates in one fixed processing order -- never a
    queue or priority scheme, and never a judge of eligibility: it only
    sorts candidates the candidate service already reports as eligible.

    Order: reason precedence (invalidated, then expired), then the
    candidate's own eligible_since (expiration deadline; created_at where
    none is recorded), oldest first, then created_at, then schedule_id
    as the final stable tie-break. The result therefore never depends on
    the order candidates were supplied in.

    When candidates are supplied, any that is for another task, or is no
    longer a cleanup candidate right now (e.g. its schedule has since
    become active or already been cleaned), is dropped rather than
    ordered, and a repeated schedule_id is kept once. Writes nothing.
    """

    def __init__(self, candidate_service: LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService = None):
        self._candidate_service = (
            candidate_service
            if candidate_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService()
        )

    def order(
        self, task_id: str, candidates=None, now: Optional[datetime] = None
    ) -> tuple:
        """task_id's cleanup candidates in processing order: the given
        candidates (re-checked as still eligible), or every current
        candidate when None.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupOrderingError: If
                task_id is not a non-empty string, candidates is given
                and holds anything but cleanup candidates, or now is
                given and is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupOrderingError(
                "task_id is required and must be a non-empty string"
            )
        if now is not None and not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupOrderingError("now must be a datetime when given")

        if candidates is None:
            eligible = list(self._candidate_service.find(task_id, now=now))
        else:
            eligible, seen = [], set()
            for candidate in candidates:
                if not isinstance(candidate, AgentTaskRecoveryScheduleCleanupCandidate):
                    raise InvalidAgentTaskRecoveryScheduleCleanupOrderingError(
                        "candidates must be AgentTaskRecoveryScheduleCleanupCandidate values"
                    )
                if candidate.task_id != task_id or candidate.schedule_id in seen:
                    continue
                if self._candidate_service.is_candidate(task_id, candidate.schedule_id, now=now):
                    seen.add(candidate.schedule_id)
                    eligible.append(candidate)

        return tuple(sorted(eligible, key=self._sort_key))

    @staticmethod
    def _sort_key(candidate: AgentTaskRecoveryScheduleCleanupCandidate) -> tuple:
        return (
            _REASON_PRECEDENCE.get(candidate.reason, len(_REASON_PRECEDENCE)),
            candidate.eligible_since if candidate.eligible_since is not None else candidate.created_at,
            candidate.created_at,
            candidate.schedule_id,
        )
