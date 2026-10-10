from .research_workspace_consumer_projection_readiness_directive import (
    ResearchWorkspaceConsumerProjectionReadinessDirective,
)

from .research_workspace_consumer_projection_readiness_rationale import (
    ResearchWorkspaceConsumerProjectionReadinessRationale,
)

from .research_workspace_consumer_projection_readiness_response_package import (
    ResearchWorkspaceConsumerProjectionReadinessResponsePackage,
)

from .research_workspace_consumer_projection_readiness_response_package_error import (
    ResearchWorkspaceConsumerProjectionReadinessResponsePackageError,
)


class ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder:
    """
    Validates and combines an existing readiness directive
    (Commit #10) and readiness rationale (Commit #11) into one
    immutable, portable response package.

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
            ResearchWorkspaceConsumerProjectionReadinessDirective
        ),
        rationale: (
            ResearchWorkspaceConsumerProjectionReadinessRationale
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessResponsePackage:
        """
        Build a response package from a directive and a rationale.

        Args:
            directive: The readiness directive to package
            rationale: The readiness rationale describing the same directive

        Returns:
            An immutable response package

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageError:
                If the two artifacts do not describe the same
                projection, or their recommendation/priority disagree
        """

        self._validate_alignment(directive=directive, rationale=rationale)

        return ResearchWorkspaceConsumerProjectionReadinessResponsePackage(
            projection_name=directive.projection_name,
            recommendation=directive.recommendation,
            priority=directive.priority,
            reason=rationale.reason,
            summary=rationale.summary,
            action_required=directive.action_required,
        )

    def _validate_alignment(self, *, directive, rationale):
        if directive.projection_name != rationale.projection_name:
            raise ResearchWorkspaceConsumerProjectionReadinessResponsePackageError(
                "Cannot build a response package from a directive and "
                f"rationale describing different projections: "
                f"'{directive.projection_name}' vs "
                f"'{rationale.projection_name}'"
            )

        if directive.recommendation != rationale.recommendation:
            raise ResearchWorkspaceConsumerProjectionReadinessResponsePackageError(
                f"Directive recommendation '{directive.recommendation.value}' "
                f"does not match rationale recommendation "
                f"'{rationale.recommendation.value}'"
            )

        if directive.priority != rationale.priority:
            raise ResearchWorkspaceConsumerProjectionReadinessResponsePackageError(
                f"Directive priority '{directive.priority.value}' does not "
                f"match rationale priority '{rationale.priority.value}'"
            )
