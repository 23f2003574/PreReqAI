from .research_workspace_consumer_projection_freshness_evaluation import (
    ResearchWorkspaceConsumerProjectionFreshnessEvaluation,
)

from .research_workspace_consumer_projection_freshness_policy_not_found_error import (
    ResearchWorkspaceConsumerProjectionFreshnessPolicyNotFoundError,
)

from .research_workspace_consumer_projection_freshness_reason import (
    ResearchWorkspaceConsumerProjectionFreshnessReason,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)


_DEFAULT_MAXIMUM_FUTURE_SKEW_MS = 5000.0


class ResearchWorkspaceConsumerProjectionFreshnessEvaluator:
    """
    Stateless, application-scoped
    evaluator that classifies a source
    timestamp as fresh, stale, or
    unusable against its registered
    policy at a given observation time.
    """

    def __init__(

        self,

        *,

        policy_registry,

        maximum_future_skew_ms=(

            _DEFAULT_MAXIMUM_FUTURE_SKEW_MS
        ),

    ):

        self.policy_registry = (
            policy_registry
        )

        self.maximum_future_skew_ms = (
            maximum_future_skew_ms
        )

    def evaluate(

        self,

        *,

        source_name,

        source_timestamp,

        evaluated_at,

    ):

        if source_timestamp.tzinfo is None:

            raise ValueError(

                "Freshness source "
                "timestamp for "
                f"'{source_name}' must "
                "be timezone-aware"
            )

        if evaluated_at.tzinfo is None:

            raise ValueError(

                "Freshness evaluation "
                "time must be "
                "timezone-aware"
            )

        policy = (

            self.policy_registry
            .get_policy(
                source_name
            )
        )

        if policy is None:

            raise (

                ResearchWorkspaceConsumerProjectionFreshnessPolicyNotFoundError(
                    source_name
                )
            )

        skew_ms = (

            (

                source_timestamp

                - evaluated_at
            )
            .total_seconds()

            * 1000
        )

        if (

            skew_ms

            > self.maximum_future_skew_ms
        ):

            return (

                ResearchWorkspaceConsumerProjectionFreshnessEvaluation(

                    source_name=(
                        source_name
                    ),

                    status=(

                        ResearchWorkspaceConsumerProjectionFreshnessStatus
                        .UNUSABLE
                    ),

                    reason=(

                        ResearchWorkspaceConsumerProjectionFreshnessReason
                        .SOURCE_TIMESTAMP_IN_FUTURE
                    ),

                    source_timestamp=(
                        source_timestamp
                    ),

                    evaluated_at=(
                        evaluated_at
                    ),

                    age_ms=0.0,

                    fresh_for_ms=(
                        policy.fresh_for_ms
                    ),

                    usable_for_ms=(
                        policy.usable_for_ms
                    ),
                )
            )

        age_ms = max(

            0.0,

            (

                evaluated_at

                - source_timestamp
            )
            .total_seconds()

            * 1000,
        )

        if age_ms <= policy.fresh_for_ms:

            status = (

                ResearchWorkspaceConsumerProjectionFreshnessStatus
                .FRESH
            )

            reason = (

                ResearchWorkspaceConsumerProjectionFreshnessReason
                .WITHIN_FRESH_WINDOW
            )

        elif (

            age_ms

            <= policy.usable_for_ms
        ):

            status = (

                ResearchWorkspaceConsumerProjectionFreshnessStatus
                .STALE
            )

            reason = (

                ResearchWorkspaceConsumerProjectionFreshnessReason
                .OUTSIDE_FRESH_WINDOW
            )

        else:

            status = (

                ResearchWorkspaceConsumerProjectionFreshnessStatus
                .UNUSABLE
            )

            reason = (

                ResearchWorkspaceConsumerProjectionFreshnessReason
                .OUTSIDE_USABLE_WINDOW
            )

        return (

            ResearchWorkspaceConsumerProjectionFreshnessEvaluation(

                source_name=source_name,

                status=status,

                reason=reason,

                source_timestamp=(
                    source_timestamp
                ),

                evaluated_at=(
                    evaluated_at
                ),

                age_ms=age_ms,

                fresh_for_ms=(
                    policy.fresh_for_ms
                ),

                usable_for_ms=(
                    policy.usable_for_ms
                ),
            )
        )
