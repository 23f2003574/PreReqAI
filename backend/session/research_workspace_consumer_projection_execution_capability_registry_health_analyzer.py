from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_health_analysis_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError,
)

from .research_workspace_consumer_projection_execution_capability_registry_health_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthReport,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer:
    """
    Aggregates health statistics for a consumer projection
    execution capability registry, for diagnostics and monitoring.

    The analyzer's responsibility is aggregation, not inference. It
    does NOT modify the registry, modify packages, recompute
    decisions, reorder entries, or derive metrics beyond the counts
    below.

    The analyzer is:
    - Stateless: No instance state
    - Deterministic: Same registry state always produces the same
      report
    - Side-effect free: Never mutates the registry or its packages
    """

    def analyze(

        self,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthReport:
        """
        Analyze the health of a consumer projection execution
        capability registry.

        Args:
            registry: The registry to analyze

        Returns:
            An immutable health report aggregating executability
            and decision counts across every registered package

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError:
                If the registry is None, is not a registry, or
                contains an entry that cannot be inspected
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError(
                    "Cannot analyze a None registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError(
                    "Cannot analyze registry: registry must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry."
                )
            )

        total_projections = 0

        executable_projections = 0

        non_executable_projections = 0

        accepted_projections = 0

        review_projections = 0

        rejected_projections = 0

        for projection_name in registry.list_projection_names():

            package = registry.get(
                projection_name
            )

            try:

                executable = (
                    package.executable
                )

                decision = (
                    package.decision
                )

            except AttributeError as error:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError(
                        "Cannot analyze registry: projection "
                        f"'{projection_name}' cannot be inspected "
                        f"as an execution capability decision "
                        f"package ({error})."
                    )
                ) from error

            total_projections += 1

            if executable:

                executable_projections += 1

            else:

                non_executable_projections += 1

            if (

                decision

                == ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
            ):

                accepted_projections += 1

            elif (

                decision

                == ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW
            ):

                review_projections += 1

            elif (

                decision

                == ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT
            ):

                rejected_projections += 1

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthReport(

                total_projections=total_projections,

                executable_projections=executable_projections,

                non_executable_projections=non_executable_projections,

                accepted_projections=accepted_projections,

                review_projections=review_projections,

                rejected_projections=rejected_projections,
            )
        )
