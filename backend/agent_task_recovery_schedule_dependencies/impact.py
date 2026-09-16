from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_scheduling import (
    CANCELLED,
    INVALIDATED,
    LLMAgentTaskRecoveryPreflightSchedulingService,
)

from .models import FAILED, UNKNOWN
from .reconciliation import LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService
from .timeout import TIMED_OUT

NO_IMPACT = "no_impact"
REVALIDATION_REQUIRED = "revalidation_required"
WAITING_REQUIRED = "waiting_required"
ESCALATION_REQUIRED = "escalation_required"
SCHEDULE_NO_LONGER_VIABLE = "schedule_no_longer_viable"
IMPACT_CATEGORIES = frozenset(
    {NO_IMPACT, REVALIDATION_REQUIRED, WAITING_REQUIRED, ESCALATION_REQUIRED, SCHEDULE_NO_LONGER_VIABLE}
)


class InvalidAgentTaskRecoveryScheduleDependencyImpactError(ValueError):
    """Raised when analyze()/analyze_schedule() is given invalid
    arguments, or analyze_schedule() names a schedule that does not
    exist for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyImpactOutcome:
    """One schedule's own complete, explainable impact classification --
    never a bare label (Rule: "Include affected schedule/preflight IDs
    and supporting dependency evidence" / "Make results deterministic
    and auditable").

    category is exactly one of IMPACT_CATEGORIES, or None when
    evidence_sufficient is False (Rule: "Do not infer impact when
    dependency evidence is incomplete" -- Commit #2's own
    reliable=False/UNDETERMINED is reused verbatim as this exact
    condition, never re-derived).

    dependency_state is Commit #1/#2's own observation.state
    (ready/blocked/failed/unknown), changes is Commit #2's own
    AgentTaskRecoveryScheduleDependencyChange entries for THIS pass
    (empty on a first-ever reconciliation, or when nothing changed),
    and dependency_evidence is that same observation's own blockers --
    all three carried through unchanged, never recomputed a second way.
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    dependency_id: Optional[str]
    category: Optional[str]
    evidence_sufficient: bool
    dependency_state: Optional[str]
    changes: tuple
    dependency_evidence: tuple
    reason: str
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyImpactResult:
    """analyze()'s own complete report -- every schedule for task_id
    (Rule: "Identify schedules affected by the dependency change"),
    narrowed to dependency_id when one is given."""

    task_id: str
    dependency_id: Optional[str]
    outcomes: tuple
    checked_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService:
    """Classifies what a dependency change means for task_id's own
    scheduled recovery work -- never a second dependency resolver or
    decision engine (Rule: "Do not create another dependency resolver
    or decision engine"): every fact here is read straight from an
    existing collaborator, and analyze()/analyze_schedule() never
    reschedule, dispatch, cancel, block, escalate, or execute anything
    (Rule: "Read-only") -- this service only ever answers "what would
    need to happen," leaving the actual decision (calling this
    package's own Commit #3/#4/#6/#7 write paths) to its caller.

    "Compare previously recorded dependency state with current state"
    is entirely Commit #2's own reconciliation_service.reconcile() --
    its own `changes` (per-dependency newly_blocked/resolved/failed/
    removed/changed entries, diffed against that exact schedule's own
    prior observation) is reused verbatim, never a second diff
    algorithm. reconcile() itself still records one new observation row
    as a side effect, exactly as it always does for every other caller
    in this whole package (Commit #5/#6/#7/#8 all trigger it the same
    way through their own chains) -- this is Commit #2's own documented
    behavior, not a mutation this service introduces, and it never
    touches schedule/task state either way.

    Classification reuses ONLY existing thresholds/states, never a new
    formula:
        schedule_no_longer_viable: the schedule itself is already
            cancelled/unauthorized (Commit #1-of-agent_task_recovery_
            scheduling's own effective CANCELLED/INVALIDATED status),
            or Commit #2's own observation.state is FAILED or UNKNOWN
            (a dependency terminally failed/cyclic, or does not exist
            at all) -- structurally unviable, not merely waiting.
        escalation_required: observation.state is BLOCKED, and an
            optional timeout_service (Commit #6) reports the wait has
            already reached TIMED_OUT -- the exact same threshold
            Commit #7's own escalate() uses, reused verbatim.
        waiting_required: observation.state is BLOCKED and either no
            timeout_service was supplied or it has not yet timed out --
            still merely waiting (Commit #3/#4's own domain).
        revalidation_required: observation.state is READY, but Commit
            #2's own changes for this pass is non-empty -- something
            about the dependency graph genuinely changed since the last
            observation (Commit #5/#8's own domain: return it to the
            ordinary validation path).
        no_impact: observation.state is READY and changes is empty --
            nothing for this schedule to act on.
    category is deliberately left None, distinct from all five of the
    above, whenever observation.reliable is False (Rule: "Do not infer
    impact when dependency evidence is incomplete") -- evidence_sufficient
    is False in exactly this one case.

    Identifies affected schedules for a given dependency_id (Rule) using
    Commit #2's own live observation buckets (ready/pending/failed/
    blocked/unresolved/cyclic) UNION this pass's own `changes` (so a
    dependency that just resolved -- and so no longer appears in any
    bucket at all -- is still correctly attributed, unlike a bucket-only
    check would allow); a schedule already cancelled/unauthorized before
    ever reconciling is never attributed to any dependency_id filter at
    all -- there is nothing left to attribute it by.
    """

    def __init__(
        self,
        reconciliation_service: LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        timeout_service=None,
    ):
        """
        Args:
            reconciliation_service: Commit #2's own reconciliation
                service -- the sole source of dependency state/changes.
                Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService
                built over scheduling_service (no dependency_resolver of
                its own -- always reports ready with no changes, so
                every schedule would classify as no_impact; pass the
                real, wired instance for this service to ever find
                anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used to
                build defaults and for every schedule read.
            timeout_service: No default. When given, its own Commit #6
                check() distinguishes escalation_required from merely
                waiting_required; when omitted, every BLOCKED schedule
                classifies as waiting_required.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
                scheduling_service=self._scheduling_service
            )
        )
        self._timeout_service = timeout_service

    def analyze(
        self, task_id: str, dependency_id: str = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyImpactResult:
        """Classify the impact of a dependency change across every
        schedule recorded for task_id, optionally narrowed to schedules
        actually affected by dependency_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyImpactError: If
                task_id is not a non-empty string, dependency_id is
                given and is not a non-empty string, or now is given and
                is not a datetime
        """
        self._require_text(task_id, "task_id")
        if dependency_id is not None:
            self._require_text(dependency_id, "dependency_id")
        now = self._resolve_now(now)

        outcomes = []
        for schedule in self._scheduling_service.list(task_id):
            outcome, affected_ids = self._analyze_one(task_id, schedule, now)
            if dependency_id is not None:
                if dependency_id not in affected_ids:
                    continue
                outcome = replace(outcome, dependency_id=dependency_id)
            outcomes.append(outcome)

        return AgentTaskRecoveryScheduleDependencyImpactResult(
            task_id=task_id, dependency_id=dependency_id, outcomes=tuple(outcomes), checked_at=now
        )

    def analyze_schedule(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyImpactOutcome:
        """Classify the impact of a dependency change for task_id's
        exact schedule_id alone.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyImpactError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyImpactError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        outcome, _ = self._analyze_one(task_id, schedule, now)
        return outcome

    def _analyze_one(self, task_id: str, schedule, now: datetime) -> tuple:
        if schedule.status == CANCELLED:
            return self._outcome(
                schedule, None, SCHEDULE_NO_LONGER_VIABLE, True, None, (), (),
                "schedule has already been cancelled", now,
            ), set()
        if schedule.status == INVALIDATED:
            return self._outcome(
                schedule, None, SCHEDULE_NO_LONGER_VIABLE, True, None, (), (),
                "schedule is not currently authorized", now,
            ), set()

        reconciliation_result = self._reconciliation_service.reconcile(task_id, schedule.schedule_id)
        observation = reconciliation_result.observations[0]
        changes = reconciliation_result.changes
        affected_ids = self._affected_ids(observation, changes)

        if not observation.reliable:
            return self._outcome(
                schedule, None, None, False, observation.state, changes, observation.blockers,
                "dependency state could not be determined reliably", now,
            ), affected_ids

        if observation.state in (FAILED, UNKNOWN):
            evidence_text = "; ".join(observation.blockers) or "no further evidence available"
            return self._outcome(
                schedule, None, SCHEDULE_NO_LONGER_VIABLE, True, observation.state, changes, observation.blockers,
                f"dependency state is {observation.state!r}: {evidence_text}", now,
            ), affected_ids

        if not observation.ready:
            category = WAITING_REQUIRED
            reason = "dependencies are blocked: " + ("; ".join(observation.blockers) or "blocked")
            if self._timeout_service is not None:
                timeout_result = self._timeout_service.check(task_id, schedule.schedule_id, now=now)
                if timeout_result.state == TIMED_OUT:
                    category = ESCALATION_REQUIRED
                    reason = f"dependency wait has exceeded its timeout threshold: {timeout_result.reason}"
            return self._outcome(
                schedule, None, category, True, observation.state, changes, observation.blockers, reason, now,
            ), affected_ids

        if changes:
            return self._outcome(
                schedule, None, REVALIDATION_REQUIRED, True, observation.state, changes, (),
                "dependency state changed since the previous observation", now,
            ), affected_ids

        return self._outcome(
            schedule, None, NO_IMPACT, True, observation.state, changes, (),
            "no dependency change affects this schedule", now,
        ), affected_ids

    @staticmethod
    def _affected_ids(observation, changes) -> set:
        ids = {change.dependency_task_id for change in changes}
        ids |= set(observation.ready_dependencies)
        ids |= set(observation.pending_dependencies)
        ids |= set(observation.failed_dependencies)
        ids |= set(observation.blocked_dependencies)
        ids |= set(observation.unresolved_dependencies)
        ids |= set(observation.cycles)
        return ids

    @staticmethod
    def _outcome(schedule, dependency_id, category, evidence_sufficient, state, changes, evidence, reason, now):
        return AgentTaskRecoveryScheduleDependencyImpactOutcome(
            task_id=schedule.task_id, schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
            dependency_id=dependency_id, category=category, evidence_sufficient=evidence_sufficient,
            dependency_state=state, changes=tuple(changes), dependency_evidence=tuple(evidence),
            reason=reason, checked_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyImpactError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyImpactError("now must be a datetime when given")
        return now
