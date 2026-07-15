from .research_workspace_consumer_projection_execution_health_analyzer import (
    ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer,
)

from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_execution_health_transition_analyzer import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer,
)

from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)


class ResearchWorkspaceConsumerProjectionExecutionHealthTransitionEvaluator:
    """
    Convenience composition of the health analyzer (Commit #3) and
    the health transition analyzer, for callers that only have two
    raw execution receipts and want the resulting health transition
    directly.

    This is purely composition - it owns no signal-extraction,
    health-classification, or transition-resolution logic of its
    own. Each existing component keeps owning its own concern.
    """

    def __init__(
        self,
        health_analyzer: (
            ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer
        ) = None,
        transition_analyzer: (
            ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer
        ) = None,
    ):
        self._health_analyzer = (
            health_analyzer
            or ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer()
        )

        self._transition_analyzer = (
            transition_analyzer
            or ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        )

    def evaluate(
        self,
        previous: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
        current: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionHealthTransition:
        """
        Derive the health transition between two execution receipts.

        Args:
            previous: The earlier execution receipt
            current: The later execution receipt

        Returns:
            An immutable health transition between the two receipts
        """

        previous_summary = self._health_analyzer.analyze(previous)
        current_summary = self._health_analyzer.analyze(current)

        return self._transition_analyzer.analyze(
            previous_summary,
            current_summary,
        )
