from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_execution_status import (
    ResearchWorkspaceConsumerProjectionExecutionStatus,
)

from .research_workspace_consumer_projection_quality_signal import (
    ResearchWorkspaceConsumerProjectionQualitySignal,
)

from .research_workspace_consumer_projection_quality_signal_code import (
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
)

from .research_workspace_consumer_projection_quality_signal_report import (
    ResearchWorkspaceConsumerProjectionQualitySignalReport,
)

from .research_workspace_consumer_projection_quality_signal_severity import (
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


class ResearchWorkspaceConsumerProjectionQualitySignalExtractor:
    """
    Extracts compact, machine-readable quality signals from one
    finalized consumer projection execution receipt.

    The extractor performs deterministic extraction of explicit
    facts already present on the receipt - it is not a scoring
    system and does not decide whether the execution should be
    considered degraded, whether a source is stale, whether a stage
    was skipped, or whether an output is provenance-covered. Those
    decisions already exist in the receipt summaries; the extractor
    only turns them into signals.

    The extractor is:
    - Stateless: No instance state
    - Deterministic: Same receipt always produces the same report
    - Side-effect free: Never mutates the receipt
    - Receipt-only: Reads exclusively from the receipt's summaries

    The extractor does NOT access repositories, projectors, execution
    context, the clock, the fingerprint service, the freshness policy,
    the budget policy, or the provenance builder. All required facts
    already exist in the receipt.
    """

    def extract(
        self,
        receipt: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
    ) -> ResearchWorkspaceConsumerProjectionQualitySignalReport:
        """
        Extract quality signals from one execution receipt.

        Args:
            receipt: The finalized execution receipt to inspect

        Returns:
            An immutable, deterministically ordered quality signal report
        """

        signals = []

        for extract_signal in (
            self._extract_execution_degraded,
            self._extract_stale_data_used,
            self._extract_expired_data_present,
            self._extract_unknown_freshness_present,
            self._extract_budget_exhausted,
            self._extract_optional_work_skipped,
            self._extract_incomplete_provenance,
        ):
            signal = extract_signal(receipt)
            if signal is not None:
                signals.append(signal)

        signals = tuple(signals)

        has_warnings = any(
            signal.severity
            == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            for signal in signals
        )

        has_critical_signals = any(
            signal.severity
            == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL
            for signal in signals
        )

        return ResearchWorkspaceConsumerProjectionQualitySignalReport(
            execution_id=receipt.execution_id,
            projection_name=receipt.identity.projection_name,
            signals=signals,
            has_warnings=has_warnings,
            has_critical_signals=has_critical_signals,
        )

    def _extract_execution_degraded(self, receipt):
        if (
            receipt.status
            != ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        ):
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            message="Execution completed in a degraded state.",
        )

    def _extract_stale_data_used(self, receipt):
        count = receipt.freshness.stale_usable_source_count
        if count <= 0:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            value=count,
            message=(
                f"{count} source{_plural(count)} {_was_were(count)} "
                "stale but still usable."
            ),
        )

    def _extract_expired_data_present(self, receipt):
        count = receipt.freshness.expired_source_count
        if count <= 0:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL
            ),
            value=count,
            message=(
                f"{count} source{_plural(count)} {_was_were(count)} "
                "expired but still present in this completed execution."
            ),
        )

    def _extract_unknown_freshness_present(self, receipt):
        count = receipt.freshness.unknown_source_count
        if count <= 0:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            value=count,
            message=(
                f"{count} source{_plural(count)} {_was_were(count)} "
                "present with unknown freshness classification."
            ),
        )

    def _extract_budget_exhausted(self, receipt):
        if not receipt.budget.budgeted:
            return None

        if not receipt.budget.exhausted:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            message="Execution budget was exhausted.",
        )

    def _extract_optional_work_skipped(self, receipt):
        count = receipt.budget.skipped_stage_count
        if count <= 0:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            value=count,
            message=(
                f"{count} optional execution stage{_plural(count)} "
                f"{_was_were(count)} skipped."
            ),
        )

    def _extract_incomplete_provenance(self, receipt):
        count = receipt.provenance.uncovered_output_count
        if count <= 0:
            return None

        return ResearchWorkspaceConsumerProjectionQualitySignal(
            code=(
                ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE
            ),
            severity=(
                ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
            ),
            value=count,
            message=(
                f"{count} output{_plural(count)} {_was_were(count)} "
                "without provenance coverage."
            ),
        )


def _plural(count: int) -> str:
    return "" if count == 1 else "s"


def _was_were(count: int) -> str:
    return "was" if count == 1 else "were"
