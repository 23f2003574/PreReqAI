from .research_workspace_consumer_projection_execution_capability_consumer_response import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)

from .research_workspace_consumer_projection_execution_capability_decision_package_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError,
)

from .research_workspace_consumer_projection_execution_capability_decision_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageBuilder:
    """
    Validates and composes an existing execution capability decision
    snapshot and consumer response into one immutable execution
    capability decision package.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run decision resolution,
    recalculate the response, access repositories, or derive new
    policy.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same package
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        snapshot: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot
        ),
        response: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage:
        """
        Build an execution capability decision package from an
        execution capability decision snapshot and consumer
        response.

        Args:
            snapshot: The execution capability decision snapshot for
                this projection
            response: The consumer response describing the same
                projection

        Returns:
            An immutable execution capability decision package

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError:
                If the snapshot and response do not describe the
                same projection or do not agree on the resolved
                decision and executability
        """

        if response.projection_name != snapshot.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError(
                f"Cannot build an execution capability decision package: "
                f"response projection name '{response.projection_name}' "
                f"does not match snapshot projection name "
                f"'{snapshot.projection_name}'"
            )

        if response.decision != snapshot.decision:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError(
                f"Cannot build an execution capability decision package: "
                f"response decision '{response.decision}' does not match "
                f"snapshot decision '{snapshot.decision}'"
            )

        if response.executable != snapshot.executable:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError(
                f"Cannot build an execution capability decision package: "
                f"response executable flag '{response.executable}' does "
                f"not match snapshot executable flag "
                f"'{snapshot.executable}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage(
            projection_name=snapshot.projection_name,
            decision=snapshot.decision,
            executable=snapshot.executable,
            title=response.title,
            message=response.message,
        )
