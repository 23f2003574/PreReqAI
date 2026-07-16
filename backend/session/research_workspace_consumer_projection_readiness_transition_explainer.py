from .research_workspace_consumer_projection_readiness_explanation_error import (
    ResearchWorkspaceConsumerProjectionReadinessExplanationError,
)

from .research_workspace_consumer_projection_readiness_issue_change import (
    ResearchWorkspaceConsumerProjectionReadinessIssueChange,
)

from .research_workspace_consumer_projection_readiness_report import (
    ResearchWorkspaceConsumerProjectionReadinessReport,
)

from .research_workspace_consumer_projection_readiness_transition_explanation import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation,
)

from .research_workspace_consumer_projection_readiness_transition_report import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


class ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer:
    """
    Explains a Commit #4 readiness transition in terms of which
    Commit #1 readiness issue codes appeared, resolved, or persisted
    between the previous and current readiness report.

    Issue codes are ordered by first appearance: the previous
    report's issues in their existing evaluator order, then the
    current report's issues in their existing evaluator order for
    any codes not already seen. This reuses the evaluator's already-
    deterministic ordering rather than introducing a lexical sort.
    Issues are compared by code only - messages, object identity,
    and duplicate codes within a single report are all irrelevant to
    the comparison.

    The explainer consumes already-finalized artifacts only. It does
    NOT re-run readiness evaluation, recalculate the transition,
    access repositories, or read the clock.

    The explainer is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same explanation
    - Side-effect free: Never mutates either report or the transition
    """

    def explain(
        self,
        previous: (
            ResearchWorkspaceConsumerProjectionReadinessReport
        ),
        current: (
            ResearchWorkspaceConsumerProjectionReadinessReport
        ),
        transition: (
            ResearchWorkspaceConsumerProjectionReadinessTransitionReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation:
        """
        Explain a readiness transition using the issue codes it moved between.

        Args:
            previous: Readiness report for the earlier evaluation
            current: Readiness report for the later evaluation
            transition: The already-computed transition to explain

        Returns:
            An immutable, deterministically ordered explanation

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessExplanationError:
                If the reports and transition do not describe the same
                projection, or the transition does not describe the
                readiness movement between these exact two reports
        """

        if (
            previous.projection_name != current.projection_name
            or previous.projection_name != transition.projection_name
        ):
            raise ResearchWorkspaceConsumerProjectionReadinessExplanationError(
                "Cannot explain a readiness transition across different "
                f"projections: '{previous.projection_name}', "
                f"'{current.projection_name}', "
                f"'{transition.projection_name}'"
            )

        if (
            transition.previous_readiness != previous.readiness
            or transition.current_readiness != current.readiness
        ):
            raise ResearchWorkspaceConsumerProjectionReadinessExplanationError(
                "Transition readiness does not match the given reports: "
                f"transition describes "
                f"'{transition.previous_readiness.value}' -> "
                f"'{transition.current_readiness.value}', reports are "
                f"'{previous.readiness.value}' -> '{current.readiness.value}'"
            )

        previous_codes = dict.fromkeys(
            issue.code for issue in previous.issues
        )
        current_codes = dict.fromkeys(
            issue.code for issue in current.issues
        )

        all_codes = dict.fromkeys(
            list(previous_codes) + list(current_codes)
        )

        changes = tuple(
            ResearchWorkspaceConsumerProjectionReadinessIssueChange(
                code=code,
                previous=code in previous_codes,
                current=code in current_codes,
            )
            for code in all_codes
        )

        return ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation(
            projection_name=previous.projection_name,
            transition=transition.transition,
            appeared_issues=tuple(
                change.code for change in changes if change.appeared
            ),
            resolved_issues=tuple(
                change.code for change in changes if change.resolved
            ),
            persistent_issues=tuple(
                change.code for change in changes if change.persistent
            ),
            changes=changes,
        )
