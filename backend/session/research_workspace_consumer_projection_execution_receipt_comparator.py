from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_execution_receipt_comparison import (
    ResearchWorkspaceConsumerProjectionExecutionReceiptComparison,
)

from .research_workspace_consumer_projection_execution_status import (
    ResearchWorkspaceConsumerProjectionExecutionStatus,
)

from .research_workspace_consumer_projection_receipt_change_kind import (
    ResearchWorkspaceConsumerProjectionReceiptChangeKind,
)

from .research_workspace_consumer_projection_receipt_comparison_error import (
    ResearchWorkspaceConsumerProjectionReceiptComparisonError,
)

from .research_workspace_consumer_projection_receipt_field_change import (
    ResearchWorkspaceConsumerProjectionReceiptFieldChange,
)


# Dimensions that describe execution quality rather than consumer-facing
# semantic state (fingerprint) or contract identity (contract_version).
_EXECUTION_CONDITION_FIELDS = frozenset(
    {
        "status",
        "diagnostics",
        "freshness",
        "budget",
        "provenance",
    }
)


class ResearchWorkspaceConsumerProjectionExecutionReceiptComparator:
    """
    Compares two immutable consumer projection execution receipts.

    Distinguishes:
    - Semantic State Change: Did the consumer-facing projection
      content change? Determined solely from the stored fingerprint.
    - Execution Condition Change: Did execution quality change?
      (status, diagnostics, freshness, budget, provenance)

    That distinction is the central purpose of the comparator: two
    receipts can share an identical fingerprint while their execution
    conditions differ, or vice versa.

    The comparator is:
    - Stateless: No instance state
    - Deterministic: Same receipts always produce the same comparison
    - Side-effect free: Never mutates either receipt

    The comparator does NOT:
    - Recompute fingerprints
    - Inspect projection payloads
    - Resolve contract version compatibility
    - Access repositories, projection services, or the clock
    - Perform historical storage or persistence

    It operates entirely on the compact summaries already present
    on the receipts.
    """

    def compare(
        self,
        previous: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
        current: (
            ResearchWorkspaceConsumerProjectionExecutionReceipt
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionReceiptComparison:
        """
        Compare two execution receipts describing the same projection.

        Args:
            previous: The earlier execution receipt
            current: The later execution receipt

        Returns:
            An immutable comparison describing detected differences

        Raises:
            ResearchWorkspaceConsumerProjectionReceiptComparisonError:
                If the receipts describe different projections
        """

        if (
            previous.identity.projection_name
            != current.identity.projection_name
        ):
            raise ResearchWorkspaceConsumerProjectionReceiptComparisonError(
                "Cannot compare execution receipts for different "
                f"projections: '{previous.identity.projection_name}' "
                f"vs '{current.identity.projection_name}'"
            )

        changes = []

        for comparator in (
            self._compare_contract_version,
            self._compare_fingerprint,
            self._compare_status,
            self._compare_diagnostics,
            self._compare_freshness,
            self._compare_budget,
            self._compare_provenance,
        ):
            change = comparator(
                previous=previous,
                current=current,
            )
            if change is not None:
                changes.append(change)

        changes = tuple(changes)

        semantic_state_changed = (
            previous.identity.fingerprint
            != current.identity.fingerprint
        )

        execution_conditions_changed = any(
            change.field in _EXECUTION_CONDITION_FIELDS
            for change in changes
        )

        return ResearchWorkspaceConsumerProjectionExecutionReceiptComparison(
            projection_name=previous.identity.projection_name,
            previous_execution_id=previous.execution_id,
            current_execution_id=current.execution_id,
            semantic_state_changed=semantic_state_changed,
            execution_conditions_changed=execution_conditions_changed,
            overall_change=self._resolve_overall_change(changes),
            changes=changes,
        )

    def _resolve_overall_change(
        self,
        changes,
    ) -> ResearchWorkspaceConsumerProjectionReceiptChangeKind:
        if not changes:
            return (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.UNCHANGED
            )

        # Any execution-quality regression takes precedence, so a
        # regression is never hidden behind an unrelated improvement.
        has_degraded = any(
            change.field in _EXECUTION_CONDITION_FIELDS
            and change.kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            for change in changes
        )
        if has_degraded:
            return (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )

        has_improved = any(
            change.field in _EXECUTION_CONDITION_FIELDS
            and change.kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            for change in changes
        )
        if has_improved:
            return (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )

        return (
            ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )

    def _compare_contract_version(self, *, previous, current):
        prev = previous.identity.contract_version
        curr = current.identity.contract_version

        if prev == curr:
            return None

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="contract_version",
            kind=ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED,
            previous=self._format_contract_version(prev),
            current=self._format_contract_version(curr),
        )

    def _compare_fingerprint(self, *, previous, current):
        prev = previous.identity.fingerprint
        curr = current.identity.fingerprint

        if prev == curr:
            return None

        # A fingerprint difference identifies a semantic state change,
        # not an execution-quality regression or improvement.
        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="fingerprint",
            kind=ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED,
            previous=self._format_fingerprint(prev),
            current=self._format_fingerprint(curr),
        )

    def _compare_status(self, *, previous, current):
        prev = previous.status
        curr = current.status

        if prev == curr:
            return None

        if (
            prev
            == ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
            and curr
            == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        ):
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif (
            prev
            == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            and curr
            == ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        ):
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )
        else:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
            )

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="status",
            kind=kind,
            previous=prev.value,
            current=curr.value,
        )

    def _compare_diagnostics(self, *, previous, current):
        prev = previous.diagnostics
        curr = current.diagnostics

        if prev == curr:
            return None

        if curr.degraded_stage_count > prev.degraded_stage_count:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif curr.degraded_stage_count < prev.degraded_stage_count:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )
        else:
            # Stage count, reuse count, or duration differences alone
            # are not inherently better or worse - execution timing
            # can vary naturally, so no threshold is invented here.
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
            )

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="diagnostics",
            kind=kind,
            previous=self._format_diagnostics(prev),
            current=self._format_diagnostics(curr),
        )

    def _compare_freshness(self, *, previous, current):
        prev = previous.freshness
        curr = current.freshness

        if prev == curr:
            return None

        expired_delta = (
            curr.expired_source_count - prev.expired_source_count
        )
        stale_delta = (
            curr.stale_usable_source_count
            - prev.stale_usable_source_count
        )
        unknown_delta = (
            curr.unknown_source_count - prev.unknown_source_count
        )

        worsened = (
            expired_delta > 0
            or stale_delta > 0
            or unknown_delta > 0
        )
        improved = (
            expired_delta < 0
            or stale_delta < 0
            or unknown_delta < 0
        )

        if expired_delta > 0:
            # More expired sources is always treated as a regression,
            # even alongside an improvement elsewhere.
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif worsened and not improved:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif improved and not worsened:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )
        else:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
            )

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="freshness",
            kind=kind,
            previous=self._format_freshness(prev),
            current=self._format_freshness(curr),
        )

    def _compare_budget(self, *, previous, current):
        prev = previous.budget
        curr = current.budget

        if prev == curr:
            return None

        skipped_delta = (
            curr.skipped_stage_count - prev.skipped_stage_count
        )
        exhaustion_worsened = curr.exhausted and not prev.exhausted
        exhaustion_improved = prev.exhausted and not curr.exhausted

        worsened = skipped_delta > 0 or exhaustion_worsened
        improved = skipped_delta < 0 or exhaustion_improved

        if worsened and not improved:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif improved and not worsened:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )
        else:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
            )

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="budget",
            kind=kind,
            previous=self._format_budget(prev),
            current=self._format_budget(curr),
        )

    def _compare_provenance(self, *, previous, current):
        prev = previous.provenance
        curr = current.provenance

        if prev == curr:
            return None

        uncovered_delta = (
            curr.uncovered_output_count - prev.uncovered_output_count
        )

        if uncovered_delta > 0:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
            )
        elif uncovered_delta < 0:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
            )
        else:
            kind = (
                ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
            )

        return ResearchWorkspaceConsumerProjectionReceiptFieldChange(
            field="provenance",
            kind=kind,
            previous=self._format_provenance(prev),
            current=self._format_provenance(curr),
        )

    def _format_contract_version(self, value):
        if value is None:
            return "unspecified"
        return str(value)

    def _format_fingerprint(self, fingerprint):
        if fingerprint is None:
            return "unavailable"

        value = fingerprint.value
        if len(value) > 8:
            value = value[:8] + "..."

        return f"{fingerprint.algorithm.value}:{value}"

    def _format_diagnostics(self, diagnostics):
        parts = [
            f"{diagnostics.stage_count} stages",
            f"{diagnostics.degraded_stage_count} degraded",
            f"{diagnostics.reused_resolution_count} reused",
        ]

        if diagnostics.total_duration_ms is not None:
            parts.append(f"{diagnostics.total_duration_ms:.1f}ms")

        return ", ".join(parts)

    def _format_freshness(self, freshness):
        parts = []

        if freshness.fresh_source_count > 0:
            parts.append(f"{freshness.fresh_source_count} fresh")

        if freshness.stale_usable_source_count > 0:
            parts.append(
                f"{freshness.stale_usable_source_count} stale-usable"
            )

        if freshness.expired_source_count > 0:
            parts.append(f"{freshness.expired_source_count} expired")

        if freshness.unknown_source_count > 0:
            parts.append(f"{freshness.unknown_source_count} unknown")

        if not parts:
            return "no sources observed"

        return ", ".join(parts)

    def _format_budget(self, budget):
        if not budget.budgeted:
            return "unbudgeted"

        parts = [
            f"{budget.admitted_stage_count} admitted",
            f"{budget.skipped_stage_count} skipped",
        ]

        if budget.exhausted:
            parts.append("exhausted")

        return ", ".join(parts)

    def _format_provenance(self, provenance):
        total_outputs = (
            provenance.covered_output_count
            + provenance.uncovered_output_count
        )

        if total_outputs == 0:
            return "no outputs"

        return (
            f"{provenance.covered_output_count}/{total_outputs} "
            "outputs covered"
        )
