from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_receipt_change_kind import (
    ResearchWorkspaceConsumerProjectionReceiptChangeKind,
)

from .research_workspace_consumer_projection_receipt_field_change import (
    ResearchWorkspaceConsumerProjectionReceiptFieldChange,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionReceiptComparison:
    """
    Result of comparing two consumer projection execution receipts.

    Distinguishes two different kinds of change:
    - Semantic State Change: Did the consumer-facing projection
      content change? Determined solely from the stored fingerprint.
    - Execution Condition Change: Did execution quality change?
      (status, diagnostics, freshness, budget, provenance)

    Contract version differences are recorded in `changes` but do
    not count toward either semantic state or execution conditions.
    Contract compatibility semantics belong to the contract manifest
    layer, not the receipt comparator.

    Attributes:
        projection_name: Name of the compared projection
        previous_execution_id: Execution ID of the previous receipt
        current_execution_id: Execution ID of the current receipt
        semantic_state_changed: True if the stored fingerprints differ
        execution_conditions_changed: True if any execution dimension
            (status, diagnostics, freshness, budget, provenance) differs
        overall_change: Directional summary of the comparison
        changes: Stable-ordered tuple of detected field changes
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    semantic_state_changed: bool

    execution_conditions_changed: bool

    overall_change: (
        ResearchWorkspaceConsumerProjectionReceiptChangeKind
    )

    changes: tuple[
        ResearchWorkspaceConsumerProjectionReceiptFieldChange,
        ...,
    ]

    def to_dict(self):
        """
        Serialize the comparison to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "semantic_state_changed": self.semantic_state_changed,
            "execution_conditions_changed": (
                self.execution_conditions_changed
            ),
            "overall_change": self.overall_change.value,
            "changes": [
                {
                    "field": change.field,
                    "kind": change.kind.value,
                    "previous": change.previous,
                    "current": change.current,
                }
                for change in self.changes
            ],
        }
