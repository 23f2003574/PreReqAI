from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_health_signal_change import (
    ResearchWorkspaceConsumerProjectionHealthSignalChange,
)

from .research_workspace_consumer_projection_health_transition_explanation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanation,
)

from .research_workspace_consumer_projection_health_transition_explanation_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError,
)

from .research_workspace_consumer_projection_quality_signal_code import (
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
)

from .research_workspace_consumer_projection_quality_signal_report import (
    ResearchWorkspaceConsumerProjectionQualitySignalReport,
)


# Stable signal ordering established by Commit #2's extractor.
_SIGNAL_CODE_ORDER = (
    ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED,
    ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionExplainer:
    """
    Explains a Commit #4 health transition in terms of which
    Commit #2 quality signals appeared, resolved, persisted, or
    changed severity between the previous and current execution.

    The explainer consumes already-finalized artifacts only. It does
    NOT inspect execution receipts, re-extract quality signals,
    recalculate health, recalculate the transition, access
    repositories, or read the clock.

    The explainer is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same explanation
    - Side-effect free: Never mutates either report or the transition
    """

    def explain(
        self,
        *,
        previous_report: (
            ResearchWorkspaceConsumerProjectionQualitySignalReport
        ),
        current_report: (
            ResearchWorkspaceConsumerProjectionQualitySignalReport
        ),
        transition: (
            ResearchWorkspaceConsumerProjectionExecutionHealthTransition
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionExplanation:
        """
        Explain a health transition using the quality signals it moved between.

        Args:
            previous_report: Quality signal report for the previous execution
            current_report: Quality signal report for the current execution
            transition: The already-computed health transition to explain

        Returns:
            An immutable, deterministically ordered explanation

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError:
                If the reports and transition do not describe the same
                execution pair and projection, or a report contains
                duplicate signal codes
        """

        if previous_report.execution_id != transition.previous_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError(
                "Previous report execution ID "
                f"'{previous_report.execution_id}' does not match "
                f"transition previous execution ID "
                f"'{transition.previous_execution_id}'"
            )

        if current_report.execution_id != transition.current_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError(
                "Current report execution ID "
                f"'{current_report.execution_id}' does not match "
                f"transition current execution ID "
                f"'{transition.current_execution_id}'"
            )

        if (
            previous_report.projection_name != current_report.projection_name
            or previous_report.projection_name != transition.projection_name
        ):
            raise ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError(
                "Cannot explain a health transition across different "
                f"projections: '{previous_report.projection_name}', "
                f"'{current_report.projection_name}', "
                f"'{transition.projection_name}'"
            )

        previous_by_code = self._index_by_code(previous_report.signals)
        current_by_code = self._index_by_code(current_report.signals)

        appeared_signals = []
        resolved_signals = []
        persistent_signals = []
        severity_changes = []

        for code in _SIGNAL_CODE_ORDER:
            previous_signal = previous_by_code.get(code)
            current_signal = current_by_code.get(code)

            if current_signal is not None and previous_signal is None:
                appeared_signals.append(code)
            elif previous_signal is not None and current_signal is None:
                resolved_signals.append(code)
            elif previous_signal is not None and current_signal is not None:
                persistent_signals.append(code)

                if previous_signal.severity != current_signal.severity:
                    severity_changes.append(
                        ResearchWorkspaceConsumerProjectionHealthSignalChange(
                            code=code,
                            previous_severity=previous_signal.severity,
                            current_severity=current_signal.severity,
                        )
                    )

        return ResearchWorkspaceConsumerProjectionHealthTransitionExplanation(
            projection_name=previous_report.projection_name,
            previous_execution_id=previous_report.execution_id,
            current_execution_id=current_report.execution_id,
            transition=transition.kind,
            appeared_signals=tuple(appeared_signals),
            resolved_signals=tuple(resolved_signals),
            persistent_signals=tuple(persistent_signals),
            severity_changes=tuple(severity_changes),
        )

    def _index_by_code(self, signals):
        index = {}

        for signal in signals:
            if signal.code in index:
                raise ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError(
                    "Malformed quality signal report contains duplicate "
                    f"signal code '{signal.code.value}'"
                )

            index[signal.code] = signal

        return index
