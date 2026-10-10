from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .research_workspace_consumer_projection_budget_summary import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
)

from .research_workspace_consumer_projection_diagnostics_summary import (
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
)

from .research_workspace_consumer_projection_execution_status import (
    ResearchWorkspaceConsumerProjectionExecutionStatus,
)

from .research_workspace_consumer_projection_freshness_summary import (
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
)

from .research_workspace_consumer_projection_identity import (
    ResearchWorkspaceConsumerProjectionIdentity,
)

from .research_workspace_consumer_projection_provenance_summary import (
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionReceipt:
    """
    Compact immutable record of one completed consumer projection execution.

    The receipt answers:
    - What exactly was produced during this execution?
    - Under which contract?
    - With which semantic identity?
    - With what execution outcome?
    - Using what freshness state?
    - Under what budget behavior?
    - With what provenance coverage?

    The receipt is:
    - Compact: Summaries only, not full reports
    - Immutable: Frozen dataclass
    - Deterministic: Same artifacts produce same receipt
    - Derived: Built from finalized execution artifacts
    - One-per-execution: One receipt per completed projection

    The receipt does NOT embed:
    - Full projection payload
    - Full diagnostics timeline
    - Full provenance graph
    - Full budget ledger
    - Full freshness registry
    - Full execution scope

    Those remain available on the execution result for detailed inspection.

    Attributes:
        execution_id: Stable identifier for this execution instance
        observed_at: Request-scoped observation time (reused from context)
        identity: Projection identity (name, contract, fingerprint)
        status: Overall execution outcome (SUCCEEDED or DEGRADED)
        diagnostics: Summary of execution diagnostics
        freshness: Summary of source freshness classifications
        budget: Summary of budget behavior
        provenance: Summary of provenance coverage
    """

    execution_id: str

    observed_at: datetime

    identity: (
        ResearchWorkspaceConsumerProjectionIdentity
    )

    status: (
        ResearchWorkspaceConsumerProjectionExecutionStatus
    )

    diagnostics: (
        ResearchWorkspaceConsumerProjectionDiagnosticsSummary
    )

    freshness: (
        ResearchWorkspaceConsumerProjectionFreshnessSummary
    )

    budget: (
        ResearchWorkspaceConsumerProjectionBudgetSummary
    )

    provenance: (
        ResearchWorkspaceConsumerProjectionProvenanceSummary
    )

    def to_dict(self):
        """
        Serialize the receipt to a deterministic dictionary.

        The serialized form is compact and suitable for:
        - Logging
        - Debugging
        - Cross-process verification
        - Historical analysis (if persisted later)

        Does not include full projection payload or detailed reports.
        """

        return {
            "execution_id": self.execution_id,
            "observed_at": self.observed_at.isoformat(),
            "identity": {
                "projection_name": self.identity.projection_name,
                "contract_version": self.identity.contract_version,
                "fingerprint": (
                    {
                        "algorithm": self.identity.fingerprint.algorithm.value,
                        "value": self.identity.fingerprint.value,
                    }
                    if self.identity.fingerprint
                    else None
                ),
            },
            "status": self.status.value,
            "diagnostics": {
                "stage_count": self.diagnostics.stage_count,
                "degraded_stage_count": self.diagnostics.degraded_stage_count,
                "reused_resolution_count": self.diagnostics.reused_resolution_count,
                "total_duration_ms": self.diagnostics.total_duration_ms,
            },
            "freshness": {
                "observed_source_count": self.freshness.observed_source_count,
                "fresh_source_count": self.freshness.fresh_source_count,
                "stale_usable_source_count": (
                    self.freshness.stale_usable_source_count
                ),
                "expired_source_count": self.freshness.expired_source_count,
                "unknown_source_count": self.freshness.unknown_source_count,
            },
            "budget": {
                "budgeted": self.budget.budgeted,
                "admitted_stage_count": self.budget.admitted_stage_count,
                "skipped_stage_count": self.budget.skipped_stage_count,
                "exhausted": self.budget.exhausted,
            },
            "provenance": {
                "source_node_count": self.provenance.source_node_count,
                "derivation_node_count": self.provenance.derivation_node_count,
                "output_node_count": self.provenance.output_node_count,
                "edge_count": self.provenance.edge_count,
                "covered_output_count": self.provenance.covered_output_count,
                "uncovered_output_count": (
                    self.provenance.uncovered_output_count
                ),
            },
        }
