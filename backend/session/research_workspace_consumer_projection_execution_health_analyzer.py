from .research_workspace_consumer_projection_execution_health_summarizer import (
    ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer,
)

from .research_workspace_consumer_projection_execution_health_summary import (
    ResearchWorkspaceConsumerProjectionExecutionHealthSummary,
)

from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_quality_signal_extractor import (
    ResearchWorkspaceConsumerProjectionQualitySignalExtractor,
)


class ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer:
    """
    Convenience composition of the quality signal extractor (Commit #2)
    and the execution health summarizer, for callers that only care
    about the final health summary for a receipt.

    This is purely composition - it owns no signal-extraction or
    health-classification logic of its own. The extractor still owns
    signal extraction; the summarizer still owns health classification.
    """

    def __init__(
        self,
        signal_extractor: (
            ResearchWorkspaceConsumerProjectionQualitySignalExtractor
        ) = None,
        health_summarizer: (
            ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer
        ) = None,
    ):
        self._signal_extractor = (
            signal_extractor
            or ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        )

        self._health_summarizer = (
            health_summarizer
            or ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        )

    def analyze(
        self,
        receipt: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionHealthSummary:
        """
        Extract quality signals from a receipt and summarize its health.

        Args:
            receipt: The finalized execution receipt to analyze

        Returns:
            An immutable execution health summary
        """

        report = self._signal_extractor.extract(receipt)

        return self._health_summarizer.summarize(report)
