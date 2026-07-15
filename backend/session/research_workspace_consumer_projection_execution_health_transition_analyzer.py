from .research_workspace_consumer_projection_execution_health import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
)

from .research_workspace_consumer_projection_execution_health_summary import (
    ResearchWorkspaceConsumerProjectionExecutionHealthSummary,
)

from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_health_transition_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionError,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)


class ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer:
    """
    Compares two consumer projection execution health summaries
    (Commit #3) and classifies the direction of health movement
    between them.

    The analyzer operates only on existing health summaries. It does
    NOT re-extract quality signals, inspect execution receipts,
    compare fingerprints, access repositories, or read the clock.

    The analyzer is:
    - Stateless: No instance state
    - Deterministic: Same summaries always produce the same transition
    - Side-effect free: Never mutates either summary

    This is deliberately shallower than Commit #1's receipt
    comparator, which compares detailed execution characteristics.
    This analyzer only compares the single overall health
    classification produced by Commit #3.
    """

    def analyze(
        self,
        previous: (
            ResearchWorkspaceConsumerProjectionExecutionHealthSummary
        ),
        current: (
            ResearchWorkspaceConsumerProjectionExecutionHealthSummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionHealthTransition:
        """
        Compare two health summaries describing the same projection.

        Args:
            previous: The earlier execution health summary
            current: The later execution health summary

        Returns:
            An immutable health transition

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionError:
                If the summaries describe different projections
        """

        if previous.projection_name != current.projection_name:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionError(
                "Cannot analyze a health transition between different "
                f"projections: '{previous.projection_name}' vs "
                f"'{current.projection_name}'"
            )

        kind = self._resolve_transition(
            previous_health=previous.health,
            current_health=current.health,
        )

        return ResearchWorkspaceConsumerProjectionExecutionHealthTransition(
            projection_name=previous.projection_name,
            previous_execution_id=previous.execution_id,
            current_execution_id=current.execution_id,
            previous_health=previous.health,
            current_health=current.health,
            kind=kind,
        )

    def _resolve_transition(
        self,
        *,
        previous_health,
        current_health,
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionKind:
        if previous_health == current_health:
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED
            )

        if (
            current_health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
        ):
            # More specific than a generic improvement - any prior
            # concern fully clearing counts as recovery.
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
            )

        if (
            current_health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
            )

        if (
            previous_health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL
        ):
            # CRITICAL -> ATTENTION: improved, but not a full recovery.
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionKind.IMPROVED
            )

        # HEALTHY -> ATTENTION: the only remaining case.
        return (
            ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED
        )
