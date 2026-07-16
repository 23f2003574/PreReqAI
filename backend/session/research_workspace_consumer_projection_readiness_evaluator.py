from .research_workspace_consumer_projection_execution_plan import (
    ResearchWorkspaceConsumerProjectionExecutionPlan,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_issue import (
    ResearchWorkspaceConsumerProjectionReadinessIssue,
)

from .research_workspace_consumer_projection_readiness_report import (
    ResearchWorkspaceConsumerProjectionReadinessReport,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


class ResearchWorkspaceConsumerProjectionReadinessEvaluator:
    """
    Determines whether a planned consumer projection execution is
    ready to run, using only the planning artifact it is given.

    Does NOT execute projections, modify plans, access repositories,
    or read the clock.

    The evaluator is:
    - Stateless: No instance state
    - Deterministic: Same plan always produces the same report
    - Side-effect free: Never mutates the input plan
    """

    def evaluate(
        self,
        plan: ResearchWorkspaceConsumerProjectionExecutionPlan,
    ) -> ResearchWorkspaceConsumerProjectionReadinessReport:
        """
        Evaluate a projection execution plan for readiness.

        Args:
            plan: The resolved planning artifact to evaluate

        Returns:
            An immutable readiness report
        """

        issues = []
        seen_issues = set()
        blocked = False
        degraded = False

        def add_issue(code, message):
            nonlocal blocked, degraded

            key = (code, message)

            if key not in seen_issues:
                seen_issues.add(key)
                issues.append(
                    ResearchWorkspaceConsumerProjectionReadinessIssue(
                        code=code,
                        message=message,
                    )
                )

        if not plan.enabled:
            add_issue(
                "projection_disabled",
                f"projection '{plan.projection_name}' is disabled",
            )
            blocked = True

        for dependency in plan.required_dependencies:
            if not dependency.satisfied:
                add_issue(
                    "missing_dependency",
                    f"required dependency '{dependency.name}' "
                    "is not satisfied",
                )
                blocked = True
            elif dependency.degraded:
                add_issue(
                    "degraded_dependency",
                    f"required dependency '{dependency.name}' is "
                    "satisfied via a degraded path",
                )
                degraded = True

        for source in plan.required_sources:
            if source.expired:
                add_issue(
                    "expired_source",
                    f"required source '{source.name}' has expired",
                )
                blocked = True
            elif source.stale_usable:
                add_issue(
                    "stale_usable_source",
                    f"required source '{source.name}' is stale "
                    "but usable",
                )
                degraded = True

        if not plan.budget_available:
            add_issue(
                "budget_exhausted",
                "execution budget is exhausted",
            )
            blocked = True

        for stage in plan.stages:
            if stage.will_execute:
                continue

            if (
                stage.requirement
                == ResearchWorkspaceConsumerProjectionStageRequirement.MANDATORY
            ):
                add_issue(
                    "mandatory_stage_impossible",
                    f"mandatory stage '{stage.name}' cannot execute",
                )
                blocked = True
            else:
                add_issue(
                    "optional_stage_skipped",
                    f"optional stage '{stage.name}' will be skipped",
                )
                degraded = True

        if blocked:
            readiness = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
        elif degraded:
            readiness = (
                ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
            )
        else:
            readiness = ResearchWorkspaceConsumerProjectionReadiness.READY

        return ResearchWorkspaceConsumerProjectionReadinessReport(
            projection_name=plan.projection_name,
            readiness=readiness,
            executable=(
                readiness
                != ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
            ),
            issues=tuple(issues),
        )
