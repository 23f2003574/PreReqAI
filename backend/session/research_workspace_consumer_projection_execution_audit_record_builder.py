from .research_workspace_consumer_projection_execution_audit_record import (
    ResearchWorkspaceConsumerProjectionExecutionAuditRecord,
)

from .research_workspace_consumer_projection_execution_audit_record_error import (
    ResearchWorkspaceConsumerProjectionExecutionAuditRecordError,
)

from .research_workspace_consumer_projection_execution_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder:
    """
    Builds a portable execution audit record from an existing
    execution snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run any policy
    resolution, write logs, publish events, or access repositories.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same snapshot always produces the same record
    - Side-effect free: Never mutates the input snapshot
    """

    def build(
        self,
        snapshot: ResearchWorkspaceConsumerProjectionExecutionSnapshot,
    ) -> ResearchWorkspaceConsumerProjectionExecutionAuditRecord:
        """
        Build an execution audit record from an execution snapshot.

        Args:
            snapshot: The execution snapshot to compose into a
                record

        Returns:
            An immutable execution audit record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordError:
                If the snapshot's projection name is empty
        """

        if not snapshot.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionAuditRecordError(
                "Cannot build an execution audit record: "
                "projection name must be non-empty"
            )

        return ResearchWorkspaceConsumerProjectionExecutionAuditRecord(
            projection_name=snapshot.projection_name,
            outcome=snapshot.outcome,
            verdict=snapshot.verdict,
            authorization=snapshot.authorization,
            ready_for_execution=snapshot.ready_for_execution,
            summary=snapshot.description,
        )
