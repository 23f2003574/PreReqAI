from datetime import (
    datetime,
)

from .research_workspace_consumer_projection_budget_snapshot import (
    ResearchWorkspaceConsumerProjectionBudgetSnapshot,
)

from .research_workspace_consumer_projection_budget_summarizer import (
    ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_diagnostics_summarizer import (
    ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer,
)

from .research_workspace_consumer_projection_execution_outcome_resolver import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver,
)

from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
)

from .research_workspace_consumer_projection_freshness_summarizer import (
    ResearchWorkspaceConsumerProjectionFreshnessSummarizer,
)

from .research_workspace_consumer_projection_provenance_report import (
    ResearchWorkspaceConsumerProjectionProvenanceReport,
)

from .research_workspace_consumer_projection_provenance_summarizer import (
    ResearchWorkspaceConsumerProjectionProvenanceSummarizer,
)

from .research_workspace_consumer_projection_receipt_verification_issue import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssue,
)

from .research_workspace_consumer_projection_receipt_verification_issue_code import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode,
)

from .research_workspace_consumer_projection_receipt_verification_report import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationReport,
)

from .research_workspace_consumer_projection_receipt_verification_status import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier:
    """
    Verifies receipts against finalized execution artifacts.

    The verifier:
    - Re-derives compact summaries using the same pure summarizers
    - Compares them with the receipt
    - Reports mismatches

    The verifier does NOT:
    - Execute projections again
    - Resolve repositories again
    - Recompute domain decisions
    - Rebuild consumer state
    - Call repositories, projectors, domain services, clock, or external APIs
    - Recompute freshness
    - Recompute projection fingerprint
    - Mutate anything

    Verification is pure cross-layer consistency checking.
    The verifier is stateless - no previous receipt or verification state is stored.
    """

    def __init__(
        self,
        *,
        diagnostics_summarizer: (
            ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer
        ) = None,
        freshness_summarizer: (
            ResearchWorkspaceConsumerProjectionFreshnessSummarizer
        ) = None,
        budget_summarizer: (
            ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer
        ) = None,
        provenance_summarizer: (
            ResearchWorkspaceConsumerProjectionProvenanceSummarizer
        ) = None,
        outcome_resolver: (
            ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver
        ) = None,
    ):

        self._diagnostics_summarizer = (
            diagnostics_summarizer
            or ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        )

        self._freshness_summarizer = (
            freshness_summarizer
            or ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        )

        self._budget_summarizer = (
            budget_summarizer
            or ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        )

        self._provenance_summarizer = (
            provenance_summarizer
            or ResearchWorkspaceConsumerProjectionProvenanceSummarizer()
        )

        self._outcome_resolver = (
            outcome_resolver
            or ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        )

    def verify(
        self,
        *,
        receipt: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
        execution_id: str,
        observed_at: datetime,
        projection_name: str,
        contract_version: str = None,
        fingerprint_snapshot: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ) = None,
        diagnostic_report: (
            ResearchWorkspaceConsumerProjectionDiagnosticReport
        ) = None,
        provenance_report: (
            ResearchWorkspaceConsumerProjectionProvenanceReport
        ) = None,
        budget_snapshot: (
            ResearchWorkspaceConsumerProjectionBudgetSnapshot
        ) = None,
    ) -> ResearchWorkspaceConsumerProjectionReceiptVerificationReport:
        """
        Verify a receipt against finalized execution artifacts.

        Args:
            receipt: The receipt to verify
            execution_id: Execution identifier from request scope
            observed_at: Request-scoped observation time
            projection_name: Name of the projection that was executed
            contract_version: Optional contract version active at execution time
            fingerprint_snapshot: Finalized fingerprint snapshot
            diagnostic_report: Finalized diagnostic report
            provenance_report: Finalized provenance report
            budget_snapshot: Finalized budget snapshot

        Returns:
            Verification report with status and any detected issues
        """

        issues = []

        # Verification Rule 1: Projection Name
        if receipt.identity.projection_name != projection_name:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.PROJECTION_NAME_MISMATCH
                    ),
                    message=(
                        f"Receipt projection name '{receipt.identity.projection_name}' "
                        f"does not match execution projection name '{projection_name}'"
                    ),
                    expected=projection_name,
                    actual=receipt.identity.projection_name,
                )
            )

        # Verification Rule 2: Contract Version
        if receipt.identity.contract_version != contract_version:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.CONTRACT_VERSION_MISMATCH
                    ),
                    message=(
                        f"Receipt contract version '{receipt.identity.contract_version}' "
                        f"does not match execution contract version '{contract_version}'"
                    ),
                    expected=str(contract_version),
                    actual=str(receipt.identity.contract_version),
                )
            )

        # Verification Rule 3: Fingerprint
        expected_fingerprint = (
            fingerprint_snapshot.overall
            if fingerprint_snapshot
            else None
        )
        if receipt.identity.fingerprint != expected_fingerprint:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.FINGERPRINT_MISMATCH
                    ),
                    message=(
                        "Receipt fingerprint does not match execution fingerprint snapshot"
                    ),
                    expected=(
                        expected_fingerprint.value
                        if expected_fingerprint
                        else None
                    ),
                    actual=(
                        receipt.identity.fingerprint.value
                        if receipt.identity.fingerprint
                        else None
                    ),
                )
            )

        # Verification Rule 4: Execution Identifier
        if receipt.execution_id != execution_id:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.EXECUTION_ID_MISMATCH
                    ),
                    message=(
                        f"Receipt execution ID '{receipt.execution_id}' "
                        f"does not match execution ID '{execution_id}'"
                    ),
                    expected=execution_id,
                    actual=receipt.execution_id,
                )
            )

        # Verification Rule 5: Observation Time
        if receipt.observed_at != observed_at:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.OBSERVATION_TIME_MISMATCH
                    ),
                    message=(
                        f"Receipt observation time '{receipt.observed_at.isoformat()}' "
                        f"does not match execution observation time '{observed_at.isoformat()}'"
                    ),
                    expected=observed_at.isoformat(),
                    actual=receipt.observed_at.isoformat(),
                )
            )

        # Verification Rule 6: Diagnostics Summary
        expected_diagnostics_summary = (
            self._diagnostics_summarizer.summarize(
                report=diagnostic_report,
            )
        )
        if (
            receipt.diagnostics.stage_count
            != expected_diagnostics_summary.stage_count
            or receipt.diagnostics.degraded_stage_count
            != expected_diagnostics_summary.degraded_stage_count
            or receipt.diagnostics.reused_resolution_count
            != expected_diagnostics_summary.reused_resolution_count
            or receipt.diagnostics.total_duration_ms
            != expected_diagnostics_summary.total_duration_ms
        ):
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.DIAGNOSTICS_SUMMARY_MISMATCH
                    ),
                    message=(
                        "Receipt diagnostics summary does not match "
                        "derived summary from diagnostic report"
                    ),
                )
            )

        # Verification Rule 7: Freshness Summary
        expected_freshness_summary = (
            self._freshness_summarizer.summarize(
                report=diagnostic_report,
            )
        )
        if (
            receipt.freshness.observed_source_count
            != expected_freshness_summary.observed_source_count
            or receipt.freshness.fresh_source_count
            != expected_freshness_summary.fresh_source_count
            or receipt.freshness.stale_usable_source_count
            != expected_freshness_summary.stale_usable_source_count
            or receipt.freshness.expired_source_count
            != expected_freshness_summary.expired_source_count
            or receipt.freshness.unknown_source_count
            != expected_freshness_summary.unknown_source_count
        ):
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.FRESHNESS_SUMMARY_MISMATCH
                    ),
                    message=(
                        "Receipt freshness summary does not match "
                        "derived summary from diagnostic report"
                    ),
                )
            )

        # Verification Rule 8: Budget Summary
        expected_budget_summary = self._budget_summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )
        if (
            receipt.budget.budgeted != expected_budget_summary.budgeted
            or receipt.budget.admitted_stage_count
            != expected_budget_summary.admitted_stage_count
            or receipt.budget.skipped_stage_count
            != expected_budget_summary.skipped_stage_count
            or receipt.budget.exhausted != expected_budget_summary.exhausted
        ):
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.BUDGET_SUMMARY_MISMATCH
                    ),
                    message=(
                        "Receipt budget summary does not match "
                        "derived summary from budget snapshot and diagnostic report"
                    ),
                )
            )

        # Verification Rule 9: Provenance Summary
        expected_provenance_summary = (
            self._provenance_summarizer.summarize(
                report=provenance_report,
            )
        )
        if (
            receipt.provenance.source_node_count
            != expected_provenance_summary.source_node_count
            or receipt.provenance.derivation_node_count
            != expected_provenance_summary.derivation_node_count
            or receipt.provenance.output_node_count
            != expected_provenance_summary.output_node_count
            or receipt.provenance.edge_count
            != expected_provenance_summary.edge_count
            or receipt.provenance.covered_output_count
            != expected_provenance_summary.covered_output_count
            or receipt.provenance.uncovered_output_count
            != expected_provenance_summary.uncovered_output_count
        ):
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.PROVENANCE_SUMMARY_MISMATCH
                    ),
                    message=(
                        "Receipt provenance summary does not match "
                        "derived summary from provenance report"
                    ),
                )
            )

        # Verification Rule 10: Execution Status
        expected_status = self._outcome_resolver.resolve(
            diagnostics=expected_diagnostics_summary,
            freshness=expected_freshness_summary,
            budget=expected_budget_summary,
            provenance=expected_provenance_summary,
        )
        if receipt.status != expected_status:
            issues.append(
                ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
                    code=(
                        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.EXECUTION_STATUS_MISMATCH
                    ),
                    message=(
                        f"Receipt status '{receipt.status.value}' "
                        f"does not match resolved status '{expected_status.value}' "
                        "from execution summaries"
                    ),
                    expected=expected_status.value,
                    actual=receipt.status.value,
                )
            )

        # Build verification report
        status = (
            ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.VERIFIED
            if not issues
            else ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID
        )

        return ResearchWorkspaceConsumerProjectionReceiptVerificationReport(
            status=status,
            issues=tuple(issues),
        )
