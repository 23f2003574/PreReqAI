from .decision_change_impact import LLMAgentTaskRecoveryExecutionDecisionChangeImpactService
from .decision_impact_invalidation_plan import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService
from .decision_impact_staleness import LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService
from .models import (
    ARTIFACT_FRESH,
    ARTIFACT_UNKNOWN,
    IMPACT_PLAN_VALIDATION_INVALID,
    IMPACT_PLAN_VALIDATION_VALID,
    INVALIDATION_MANUAL_REVIEW,
    RESOLUTION_RESOLVED,
)
from .models import AgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationResult as _Result

_MATCHED_FIELDS = ("artifact_type", "action", "mechanism", "evidence_required", "depends_on")


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError(ValueError):
    """Raised when validate() is given an invalid task_id or no plan."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService:
    """Validates an impact-invalidation plan (#3) against CURRENT state
    before any stale artifact is touched -- never trusting the old plan:
    the plan's own decision pair is re-analysed through the change-impact
    service (#1), re-checked through the staleness service (#2) and
    re-planned through the plan service (#3), and the given plan is
    compared with that item by item. No second planner, and nothing is
    ever invalidated, refreshed or revalidated here.

    Fails closed: a plan without its decision pair, an artifact whose
    version is now unknown, a plan whose decision is no longer the
    authoritative one (when a supersession resolution service is given),
    or any stale, missing, duplicated, reordered or altered item makes the
    plan INVALID.
    """

    def __init__(
        self,
        impact_service: LLMAgentTaskRecoveryExecutionDecisionChangeImpactService = None,
        staleness_service: LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService = None,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService = None,
        supersession_resolution_service=None,
    ):
        """impact_service/staleness_service must be wired to the same
        stores the plan was built from."""
        self._impact_service = impact_service or LLMAgentTaskRecoveryExecutionDecisionChangeImpactService()
        self._staleness_service = staleness_service or LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService()
        self._plan_service = plan_service or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
        self._resolution_service = supersession_resolution_service

    def validate(self, task_id: str, plan) -> _Result:
        """Validate plan for task_id against current state.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError:
                If task_id is not a non-empty string or plan is None
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError(
                "task_id is required and must be a non-empty string"
            )
        if plan is None:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError("plan is required")

        issues = []
        if plan.task_id != task_id:
            issues.append(f"the plan was made for task {plan.task_id!r}, not {task_id!r}")
        if not plan.previous_decision_id or not plan.current_decision_id:
            issues.append("the plan does not record the decision change it was made for; its versions are ambiguous")
            return self._result(task_id, issues, (), ())

        if self._resolution_service is not None:
            resolution = self._resolution_service.resolve(task_id)
            if resolution.resolution_state != RESOLUTION_RESOLVED:
                issues.append(f"the authoritative decision cannot be established ({resolution.resolution_state})")
            elif resolution.terminal_decision_id != plan.current_decision_id:
                issues.append(
                    f"the plan targets decision {plan.current_decision_id}, but the authoritative decision is now "
                    f"{resolution.terminal_decision_id}"
                )

        impact = self._impact_service.analyze(task_id, plan.previous_decision_id, plan.current_decision_id)
        staleness = self._staleness_service.check(task_id, impact)
        current_plan = self._plan_service.plan(task_id, staleness)
        artifacts = {f"{a.kind}:{a.reference}": a for a in staleness.artifacts}
        expected = {item.artifact_id: item for item in current_plan.items}

        seen, positions, validated = {}, {}, []
        for index, item in enumerate(plan.items):
            aid = item.artifact_id
            if aid in seen:
                issues.append(
                    f"artifact {aid} is planned more than once"
                    + ("" if seen[aid] == item else " with conflicting actions")
                )
                continue
            seen[aid] = item
            positions[aid] = index
            item_issues = []

            artifact = artifacts.get(aid)
            if artifact is None:
                item_issues.append(f"artifact {aid} no longer exists or no longer belongs to this decision change")
            elif artifact.status == ARTIFACT_FRESH:
                item_issues.append(f"artifact {aid} has already been refreshed; it must not be {item.action}d")
            elif artifact.status == ARTIFACT_UNKNOWN and item.action != INVALIDATION_MANUAL_REVIEW:
                item_issues.append(f"artifact {aid}'s version is now unknown; only manual review is safe")

            if item.action == INVALIDATION_MANUAL_REVIEW and not item.execution_blocked:
                item_issues.append(f"manual_review artifact {aid} does not keep execution blocked")
            if not item.evidence_required:
                item_issues.append(f"artifact {aid} names no required evidence")
            for dependency in item.depends_on:
                if dependency not in positions:
                    item_issues.append(
                        f"artifact {aid} depends on {dependency}, which is not planned before it"
                    )

            now = expected.get(aid)
            if now is not None:
                for field_name in _MATCHED_FIELDS:
                    if getattr(item, field_name) != getattr(now, field_name):
                        item_issues.append(
                            f"artifact {aid}: planned {field_name} is not what current state supports"
                        )
                if item.execution_blocked != now.execution_blocked and not item.execution_blocked:
                    item_issues.append(f"artifact {aid} no longer keeps execution blocked as required")
            elif artifact is not None and artifact.status != ARTIFACT_FRESH:
                item_issues.append(f"artifact {aid}: no supported action exists for it now")

            issues.extend(item_issues)
            if not item_issues:
                validated.append(aid)

        for aid in expected:
            if aid not in seen:
                issues.append(f"stale artifact {aid} is missing from the plan")

        blocking = tuple(item.artifact_id for item in current_plan.items if item.execution_blocked)
        return self._result(task_id, issues, validated, blocking)

    @staticmethod
    def _result(task_id, issues, validated, blocking):
        return _Result(
            task_id=task_id, status=IMPACT_PLAN_VALIDATION_INVALID if issues else IMPACT_PLAN_VALIDATION_VALID,
            issues=tuple(issues), validated_actions=tuple(validated), blocking_actions=tuple(blocking),
        )
