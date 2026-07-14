from typing import (
    Optional,
)


class ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter:
    """
    Deterministic formatter for consumer projection execution receipts.

    Converts a ResearchWorkspaceConsumerProjectionExecutionReceipt into a
    compact, human-readable summary without:
    - Changing the receipt
    - Recomputing any execution data
    - Accessing repositories
    - Running projections
    - Performing verification
    - Adding persistence

    The formatter is:
    - Stateless: No instance state, pure function behavior
    - Deterministic: Same receipt produces same output
    - Side-effect free: No mutations or external calls

    Usage:
        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        summary = formatter.format(receipt)
    """

    def format(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        """
        Format a receipt into a compact human-readable summary.

        Args:
            receipt: The execution receipt to format

        Returns:
            A multiline string with stable field ordering and consistent
            representation of optional values.
        """
        lines = [
            self._format_execution(receipt),
            self._format_projection(receipt),
            self._format_contract(receipt),
            self._format_status(receipt),
            self._format_fingerprint(receipt),
            self._format_diagnostics(receipt),
            self._format_freshness(receipt),
            self._format_budget(receipt),
            self._format_provenance(receipt),
        ]

        return "\n".join(lines)

    def _format_execution(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        return f"Execution: {receipt.execution_id}"

    def _format_projection(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        return f"Projection: {receipt.identity.projection_name}"

    def _format_contract(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        if receipt.identity.contract_version is None:
            return "Contract: unspecified"
        return f"Contract: {receipt.identity.contract_version}"

    def _format_status(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        return f"Status: {receipt.status.value}"

    def _format_fingerprint(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        if receipt.identity.fingerprint is None:
            return "Fingerprint: unavailable"

        algorithm = receipt.identity.fingerprint.algorithm.value
        value = receipt.identity.fingerprint.value

        # Truncate fingerprint value for compactness
        if len(value) > 8:
            value = value[:8] + "..."

        return f"Fingerprint: {algorithm}:{value}"

    def _format_diagnostics(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        parts = [
            f"{receipt.diagnostics.stage_count} stages",
            f"{receipt.diagnostics.degraded_stage_count} degraded",
            f"{receipt.diagnostics.reused_resolution_count} reused",
        ]

        if receipt.diagnostics.total_duration_ms is not None:
            duration = receipt.diagnostics.total_duration_ms
            parts.append(f"{duration:.1f}ms")

        return f"Diagnostics: {', '.join(parts)}"

    def _format_freshness(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        parts = []

        if receipt.freshness.fresh_source_count > 0:
            parts.append(f"{receipt.freshness.fresh_source_count} fresh")

        if receipt.freshness.stale_usable_source_count > 0:
            parts.append(f"{receipt.freshness.stale_usable_source_count} stale-usable")

        if receipt.freshness.expired_source_count > 0:
            parts.append(f"{receipt.freshness.expired_source_count} expired")

        if receipt.freshness.unknown_source_count > 0:
            parts.append(f"{receipt.freshness.unknown_source_count} unknown")

        if not parts:
            return "Freshness: no sources observed"

        return f"Freshness: {', '.join(parts)}"

    def _format_budget(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        if not receipt.budget.budgeted:
            return "Budget: unbudgeted"

        parts = [
            f"{receipt.budget.admitted_stage_count} admitted",
            f"{receipt.budget.skipped_stage_count} skipped",
        ]

        if receipt.budget.exhausted:
            parts.append("exhausted")

        return f"Budget: {', '.join(parts)}"

    def _format_provenance(
        self,
        receipt: "ResearchWorkspaceConsumerProjectionExecutionReceipt",
    ) -> str:
        total_outputs = (
            receipt.provenance.covered_output_count
            + receipt.provenance.uncovered_output_count
        )

        if total_outputs == 0:
            return "Provenance: no outputs"

        return (
            f"Provenance: {receipt.provenance.covered_output_count}/"
            f"{total_outputs} outputs covered"
        )
