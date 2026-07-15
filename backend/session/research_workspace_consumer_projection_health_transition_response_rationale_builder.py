from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_assessment_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
)

from .research_workspace_consumer_projection_health_transition_recommendation_resolver import (
    _RECOMMENDATIONS,
)

from .research_workspace_consumer_projection_health_transition_response_directive import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
)

from .research_workspace_consumer_projection_health_transition_response_priority_resolver import (
    _PRIORITY_BY_RECOMMENDATION,
)

from .research_workspace_consumer_projection_health_transition_response_rationale import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale,
)

from .research_workspace_consumer_projection_health_transition_response_rationale_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError,
)

from .research_workspace_consumer_projection_health_transition_response_reason import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason,
)


# Direct mapping from operational assessment to reason code.
_REASON_BY_ASSESSMENT = {
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.CONDITIONS_IMPROVING
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_RECOVERED
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.MIXED_CHANGES
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_DETERIORATING
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_ESCALATED
    ),
}

# Fixed, deterministic summary text per reason code.
_SUMMARY_BY_REASON = {
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE: (
        "Execution health remained stable."
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.CONDITIONS_IMPROVING: (
        "Execution conditions are improving."
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_RECOVERED: (
        "Execution health recovered."
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.MIXED_CHANGES: (
        "Execution changes have mixed impact."
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_DETERIORATING: (
        "Execution health is deteriorating."
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_ESCALATED: (
        "Execution health escalated to a critical state."
    ),
}


class ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder:
    """
    Combines an existing operational assessment (Commit #7) and
    response directive (Commit #10) into one immutable response
    rationale: a compact reason code and stable summary text.

    The builder combines already-finalized artifacts only. It does
    NOT inspect execution receipts, inspect quality signals, rebuild
    transition explanations, recalculate recommendations,
    recalculate priorities, call an LLM, access repositories, or
    read the clock. Directive compatibility is checked by reusing
    the exact mapping tables Commit #8 and Commit #9 already define
    (`_RECOMMENDATIONS`, `_PRIORITY_BY_RECOMMENDATION`) rather than
    inventing a new compatibility rule or invoking those resolvers
    again.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same rationale
    - Side-effect free: Never mutates either input artifact
    """

    def build(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessment
        ),
        directive: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale:
        """
        Build a response rationale from an assessment and a response directive.

        Args:
            assessment: The operational assessment to explain
            directive: The response directive describing the same pair

        Returns:
            An immutable response rationale

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError:
                If the two artifacts do not describe the same execution
                pair and projection, or the directive is not compatible
                with the assessment
        """

        self._validate_alignment(assessment=assessment, directive=directive)

        reason = _REASON_BY_ASSESSMENT[assessment.assessment]
        summary = _SUMMARY_BY_REASON[reason]

        return ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale(
            projection_name=assessment.projection_name,
            previous_execution_id=assessment.previous_execution_id,
            current_execution_id=assessment.current_execution_id,
            reason=reason,
            recommendation=directive.recommendation,
            priority=directive.priority,
            summary=summary,
        )

    def _validate_alignment(self, *, assessment, directive):
        if assessment.projection_name != directive.projection_name:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
                "Cannot build a response rationale from an assessment "
                f"and directive describing different projections: "
                f"'{assessment.projection_name}' vs "
                f"'{directive.projection_name}'"
            )

        if assessment.previous_execution_id != directive.previous_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
                "Assessment previous execution ID "
                f"'{assessment.previous_execution_id}' does not match "
                f"directive previous execution ID "
                f"'{directive.previous_execution_id}'"
            )

        if assessment.current_execution_id != directive.current_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
                "Assessment current execution ID "
                f"'{assessment.current_execution_id}' does not match "
                f"directive current execution ID "
                f"'{directive.current_execution_id}'"
            )

        expected_recommendation = _RECOMMENDATIONS[assessment.assessment]
        if directive.recommendation != expected_recommendation:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
                f"Directive recommendation '{directive.recommendation.value}' "
                f"is not compatible with assessment "
                f"'{assessment.assessment.value}' (expected "
                f"'{expected_recommendation.value}')"
            )

        expected_priority = _PRIORITY_BY_RECOMMENDATION[
            directive.recommendation
        ]
        if directive.priority != expected_priority:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
                f"Directive priority '{directive.priority.value}' is not "
                f"compatible with recommendation "
                f"'{directive.recommendation.value}' (expected "
                f"'{expected_priority.value}')"
            )
