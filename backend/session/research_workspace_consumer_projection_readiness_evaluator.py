from .research_workspace_consumer_projection_execution_plan import (
    ResearchWorkspaceConsumerProjectionExecutionPlan,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_issue import (
    ResearchWorkspaceConsumerProjectionReadinessIssue,
)

from .research_workspace_consumer_projection_readiness_reason import (
    ResearchWorkspaceConsumerProjectionReadinessReason,
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
        block_reason = None

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

        def block(code, message, reason):
            nonlocal blocked, block_reason

            add_issue(code, message)
            blocked = True

            if block_reason is None:
                block_reason = reason

        def degrade(code, message):
            nonlocal degraded

            add_issue(code, message)
            degraded = True

        if not plan.enabled:
            block(
                "projection_disabled",
                f"projection '{plan.projection_name}' is disabled",
                ResearchWorkspaceConsumerProjectionReadinessReason.EXECUTION_DISABLED,
            )

        for dependency in plan.required_dependencies:
            if not dependency.satisfied:
                block(
                    "missing_dependency",
                    f"required dependency '{dependency.name}' "
                    "is not satisfied",
                    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING,
                )
            elif dependency.degraded:
                degrade(
                    "degraded_dependency",
                    f"required dependency '{dependency.name}' is "
                    "satisfied via a degraded path",
                )

        for source in plan.required_sources:
            if source.expired:
                block(
                    "expired_source",
                    f"required source '{source.name}' has expired",
                    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_SOURCE_UNAVAILABLE,
                )
            elif source.stale_usable:
                degrade(
                    "stale_usable_source",
                    f"required source '{source.name}' is stale "
                    "but usable",
                )

        if not plan.budget_available:
            block(
                "budget_exhausted",
                "execution budget is exhausted",
                ResearchWorkspaceConsumerProjectionReadinessReason.BUDGET_EXHAUSTED,
            )

        for stage in plan.stages:
            if stage.will_execute:
                continue

            if (
                stage.requirement
                == ResearchWorkspaceConsumerProjectionStageRequirement.MANDATORY
            ):
                block(
                    "mandatory_stage_impossible",
                    f"mandatory stage '{stage.name}' cannot execute",
                    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING,
                )
            else:
                degrade(
                    "optional_stage_skipped",
                    f"optional stage '{stage.name}' will be skipped",
                )

        if blocked:
            readiness = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
            reason = block_reason
        elif degraded:
            readiness = (
                ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
            )
            reason = (
                ResearchWorkspaceConsumerProjectionReadinessReason.OPTIONAL_CONSTRAINTS_PRESENT
            )
        else:
            readiness = ResearchWorkspaceConsumerProjectionReadiness.READY
            reason = (
                ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
            )

        return ResearchWorkspaceConsumerProjectionReadinessReport(
            projection_name=plan.projection_name,
            readiness=readiness,
            executable=(
                readiness
                != ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
            ),
            reason=reason,
            issues=tuple(issues),
        )
