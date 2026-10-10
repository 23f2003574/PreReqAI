from .research_workspace_consumer_projection_execution_consumer_response import (
    ResearchWorkspaceConsumerProjectionExecutionConsumerResponse,
)

from .research_workspace_consumer_projection_execution_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionPackage,
)

from .research_workspace_consumer_projection_execution_decision_package_error import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError,
)

from .research_workspace_consumer_projection_execution_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder:
    """
    Validates and composes an existing execution snapshot (Commit
    #8) and consumer response (Commit #12) into one immutable
    execution decision package.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run any policy
    resolution, recalculate the outcome, title, or message, or
    access repositories.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same package
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        snapshot: ResearchWorkspaceConsumerProjectionExecutionSnapshot,
        response: ResearchWorkspaceConsumerProjectionExecutionConsumerResponse,
    ) -> ResearchWorkspaceConsumerProjectionExecutionDecisionPackage:
        """
        Build an execution decision package from an execution
        snapshot and a consumer response.

        Args:
            snapshot: The execution snapshot for this projection
            response: The consumer response describing the same
                projection

        Returns:
            An immutable execution decision package

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError:
                If the snapshot and response do not describe the
                same projection
        """

        if response.projection_name != snapshot.projection_name:
            raise ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError(
                f"Cannot build an execution decision package: response "
                f"projection name '{response.projection_name}' does not "
                f"match snapshot projection name "
                f"'{snapshot.projection_name}'"
            )

        return ResearchWorkspaceConsumerProjectionExecutionDecisionPackage(
            projection_name=snapshot.projection_name,
            lifecycle_state=response.lifecycle_state,
            outcome=snapshot.outcome,
            ready_for_execution=snapshot.ready_for_execution,
            title=response.title,
            message=response.message,
        )
