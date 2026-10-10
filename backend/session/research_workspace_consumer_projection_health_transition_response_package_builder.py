from .research_workspace_consumer_projection_health_transition_response_directive import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
)

from .research_workspace_consumer_projection_health_transition_response_package import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage,
)

from .research_workspace_consumer_projection_health_transition_response_package_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError,
)

from .research_workspace_consumer_projection_health_transition_response_rationale import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder:
    """
    Validates and combines an existing response directive (Commit #10)
    and response rationale (Commit #11) into one immutable, portable
    response package.

    The builder performs composition only - it does not recalculate
    the recommendation, priority, reason, summary, or action
    requirement. Every decision has already been made by an earlier
    layer; this builder validates the two artifacts agree and copies
    their values through unchanged.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same package
    - Side-effect free: Never mutates either input artifact
    """

    def build(
        self,
        directive: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective
        ),
        rationale: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage:
        """
        Build a response package from a directive and a rationale.

        Args:
            directive: The response directive to package
            rationale: The response rationale describing the same directive

        Returns:
            An immutable response package

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError:
                If the two artifacts do not describe the same execution
                pair and projection, or their recommendation/priority disagree
        """

        self._validate_alignment(directive=directive, rationale=rationale)

        return ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage(
            projection_name=directive.projection_name,
            previous_execution_id=directive.previous_execution_id,
            current_execution_id=directive.current_execution_id,
            recommendation=directive.recommendation,
            priority=directive.priority,
            reason=rationale.reason,
            summary=rationale.summary,
            action_recommended=directive.action_recommended,
        )

    def _validate_alignment(self, *, directive, rationale):
        if directive.projection_name != rationale.projection_name:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
                "Cannot build a response package from a directive and "
                f"rationale describing different projections: "
                f"'{directive.projection_name}' vs "
                f"'{rationale.projection_name}'"
            )

        if directive.previous_execution_id != rationale.previous_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
                "Directive previous execution ID "
                f"'{directive.previous_execution_id}' does not match "
                f"rationale previous execution ID "
                f"'{rationale.previous_execution_id}'"
            )

        if directive.current_execution_id != rationale.current_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
                "Directive current execution ID "
                f"'{directive.current_execution_id}' does not match "
                f"rationale current execution ID "
                f"'{rationale.current_execution_id}'"
            )

        if directive.recommendation != rationale.recommendation:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
                f"Directive recommendation '{directive.recommendation.value}' "
                f"does not match rationale recommendation "
                f"'{rationale.recommendation.value}'"
            )

        if directive.priority != rationale.priority:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
                f"Directive priority '{directive.priority.value}' does not "
                f"match rationale priority '{rationale.priority.value}'"
            )
