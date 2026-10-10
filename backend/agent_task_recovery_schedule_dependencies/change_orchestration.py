from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService

from .change_audit import LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService
from .change_execution import (
    APPLIED,
    AgentTaskRecoveryScheduleDependencyChangeResult,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService,
)
from .change_planner import (
    AgentTaskRecoveryScheduleDependencyChangePlan,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner,
)


class InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError(ValueError):
    """Raised when process() is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyChangeOrchestrationResult:
    """process()'s own complete report of one full impact -> plan ->
    apply -> audit pass for task_id -- every field the Goal's own
    "Return:" list names, and nothing here re-derives any of them a
    second way:

        affected_schedule_ids: Commit #10's own plan.items, projected to
            their own schedule_id -- "affected schedules."
        planned_actions: Commit #10's own plan.items, verbatim --
            "planned actions," including any rejected-before-ever-
            attempted (conflict/insufficient-evidence) item.
        applied_actions: the subset of Commit #11's own change_result.
            results whose own status is APPLIED -- "applied actions."
        failures: the subset of Commit #11's own change_result.results
            whose own status is REJECTED or FAILED -- "failures ...
            reported explicitly" (Rule), covering both a plan Commit
            #11 itself refused (stale/conflicting/insufficient
            evidence) and one whose own execution raised unexpectedly.
        audit_records: Commit #12's own AgentTaskRecoveryScheduleDependencyChangeAudit
            entries, one per change_result.results entry, in the same
            order -- "audit references."

    plan/change_result are also carried through in full (never
    summarized away) so a caller can inspect exactly what Commit #10/#11
    themselves reported, without this class re-deriving anything from
    them a second way.
    """

    task_id: str
    dependency_id: Optional[str]
    plan: AgentTaskRecoveryScheduleDependencyChangePlan
    change_result: AgentTaskRecoveryScheduleDependencyChangeResult
    affected_schedule_ids: tuple
    planned_actions: tuple
    applied_actions: tuple
    failures: tuple
    audit_records: tuple
    processed_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleDependencyChangeOrchestrationService:
    """Closes today's whole dependency-aware scheduling loop -- never a
    new generic orchestration/workflow framework (Rule: "No new generic
    orchestration/workflow framework"): process() is a fixed, four-step
    pipeline over Commit #9-#12's own services, in their own existing
    order, and NOTHING ELSE -- no branching logic, no new decision
    rules, no new persistence of its own anywhere in this class (Rule:
    "Orchestration only; delegate all business logic").

    1. Analyze + plan: Commit #10's own planner_service.plan(task_id,
       dependency_id=dependency_id) -- which itself already calls Commit
       #9's own impact_service.analyze() internally (Rule: "Analyze
       dependency impact" / "Build the change plan" are ALREADY one
       existing call, never duplicated here as two).
    2. Apply: Commit #11's own change_service.apply(task_id, plan) --
       which itself already re-validates every item against CURRENT
       state before ever acting on it, and rejects a stale or
       conflicting one outright rather than blindly applying it (Rule:
       "Re-check current state before applying changes" / "Fail closed
       on stale/conflicting plans" both already hold by construction,
       simply by calling this exact existing method and never second-
       guessing its own verdict).
    3. Audit: Commit #12's own audit_service.record(task_id,
       schedule_id, result), once per change_result.results entry --
       covering applied, rejected, AND failed alike (Rule: "Record the
       resulting change audit"), called explicitly here even though
       change_service MAY already have its own audit_service wired in
       (Commit #12's own record() is itself idempotent/content-based,
       so a caller that also passed the SAME audit_service into
       change_service sees no duplicate either way).

    Never dispatches or executes recovery (Rule): nothing in this class,
    or in any of the four services it calls, ever touches Commit #2-of-
    agent_task_recovery_scheduling's own dispatch(), or anything from
    backend.agent_task_recovery_guardrails' own consumption service or
    agent_task_event_analytics' own execution service.

    Preserves all existing history (Rule): every write anywhere in this
    whole pipeline is one of Commit #1-#8's own already-history-
    preserving methods (Commit #4/#5/#6/#7's own state transitions,
    Commit #12's own append-only audit) -- this class itself writes
    nothing of its own.

    Idempotent by composition (Rule: "repeated processing must not
    duplicate transitions or audits"): every one of the three calls this
    class makes is already idempotent on its own terms (Commit #10's own
    plan() is a pure, deterministic read; Commit #11's own apply() only
    ever re-executes an already-idempotent underlying transition, or
    rejects outright as stale/conflicting; Commit #12's own record() is
    itself content-based idempotent) -- calling process() again for
    unchanged underlying state reproduces the identical plan, the
    identical (already-idempotent) apply() outcome, and audits nothing
    new. No special-case idempotency logic exists anywhere in this class
    itself.
    """

    def __init__(
        self,
        planner_service: LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner = None,
        change_service: LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService = None,
        audit_service: LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
    ):
        """
        Args:
            planner_service: Commit #10's own planner. Defaults to a
                fresh LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner
                built over scheduling_service (no impact_service of its
                own wired to real dependency data -- every schedule
                would plan as no_impact; pass the real, wired instance
                for this service to ever orchestrate anything
                meaningful).
            change_service: Commit #11's own execution service. Defaults
                to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService
                built over planner_service/scheduling_service (no wait_
                service/wake_service/escalation_service/timeout_service
                of its own -- every non-no_op action would then fail;
                pass the real, wired instance for this service to ever
                actually apply anything).
            audit_service: Commit #12's own audit service. Defaults to a
                fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService
                (its own fresh, empty event store -- pass the real
                instance sharing this task family's own event store for
                audits to actually be findable elsewhere).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used only
                to build the two defaults above when neither is given.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._planner_service = (
            planner_service
            if planner_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner(
                scheduling_service=self._scheduling_service
            )
        )
        self._change_service = (
            change_service
            if change_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
                planner_service=self._planner_service, scheduling_service=self._scheduling_service
            )
        )
        self._audit_service = (
            audit_service if audit_service is not None else LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService()
        )

    def process(
        self, task_id: str, dependency_id: str = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleDependencyChangeOrchestrationResult:
        """Run the full impact -> plan -> apply -> audit pipeline for
        task_id, optionally narrowed to schedules affected by
        dependency_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError:
                If task_id is not a non-empty string, dependency_id is
                given and is not a non-empty string, or now is given and
                is not a datetime
        """
        self._require_text(task_id, "task_id")
        if dependency_id is not None:
            self._require_text(dependency_id, "dependency_id")
        now = self._resolve_now(now)

        plan = self._planner_service.plan(task_id, dependency_id=dependency_id, now=now)
        change_result = self._change_service.apply(task_id, plan, now=now)

        audit_records = tuple(
            self._audit_service.record(task_id, result.schedule_id, result) for result in change_result.results
        )
        applied_actions = tuple(result for result in change_result.results if result.status == APPLIED)
        failures = tuple(result for result in change_result.results if result.status != APPLIED)
        affected_schedule_ids = tuple(item.schedule_id for item in plan.items)

        return AgentTaskRecoveryScheduleDependencyChangeOrchestrationResult(
            task_id=task_id, dependency_id=dependency_id, plan=plan, change_result=change_result,
            affected_schedule_ids=affected_schedule_ids, planned_actions=plan.items,
            applied_actions=applied_actions, failures=failures, audit_records=audit_records, processed_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError("now must be a datetime when given")
        return now
