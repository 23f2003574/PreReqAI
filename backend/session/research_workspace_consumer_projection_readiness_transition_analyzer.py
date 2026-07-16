from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_report import (
    ResearchWorkspaceConsumerProjectionReadinessReport,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)

from .research_workspace_consumer_projection_readiness_transition_error import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionError,
)

from .research_workspace_consumer_projection_readiness_transition_report import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


_SEVERITY = {
    ResearchWorkspaceConsumerProjectionReadiness.READY: 0,
    ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY: 1,
    ResearchWorkspaceConsumerProjectionReadiness.BLOCKED: 2,
}


class ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer:
    """
    Compares two consumer projection readiness reports (Commit #1/
    #2) and classifies the direction of readiness movement between
    them.

    The analyzer operates only on existing readiness reports. It
    does NOT re-run readiness evaluation, compare issue lists,
    access repositories, or read the clock.

    The analyzer is:
    - Stateless: No instance state
    - Deterministic: Same reports always produce the same transition
    - Side-effect free: Never mutates either report
    """

    def analyze(
        self,
        previous: (
            ResearchWorkspaceConsumerProjectionReadinessReport
        ),
        current: (
            ResearchWorkspaceConsumerProjectionReadinessReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessTransitionReport:
        """
        Compare two readiness reports describing the same projection.

        Args:
            previous: The earlier readiness report
            current: The later readiness report

        Returns:
            An immutable readiness transition report

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessTransitionError:
                If the reports describe different projections
        """

        if previous.projection_name != current.projection_name:
            raise ResearchWorkspaceConsumerProjectionReadinessTransitionError(
                "Cannot analyze a readiness transition between different "
                f"projections: '{previous.projection_name}' vs "
                f"'{current.projection_name}'"
            )

        transition = self._resolve_transition(
            previous_readiness=previous.readiness,
            current_readiness=current.readiness,
        )

        return ResearchWorkspaceConsumerProjectionReadinessTransitionReport(
            projection_name=previous.projection_name,
            previous_readiness=previous.readiness,
            current_readiness=current.readiness,
            transition=transition,
            previous_reason=previous.reason,
            current_reason=current.reason,
        )

    def _resolve_transition(
        self,
        *,
        previous_readiness,
        current_readiness,
    ) -> ResearchWorkspaceConsumerProjectionReadinessTransition:
        if previous_readiness == current_readiness:
            return (
                ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
            )

        if _SEVERITY[current_readiness] > _SEVERITY[previous_readiness]:
            if (
                current_readiness
                == ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
            ):
                return (
                    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
                )

            return (
                ResearchWorkspaceConsumerProjectionReadinessTransition.DEGRADED
            )

        if (
            current_readiness
            == ResearchWorkspaceConsumerProjectionReadiness.READY
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED
            )

        return (
            ResearchWorkspaceConsumerProjectionReadinessTransition.IMPROVED
        )
