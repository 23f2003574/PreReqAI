from .research_workspace_consumer_projection_freshness_policy import (
    ResearchWorkspaceConsumerProjectionFreshnessPolicy,
)


DEFAULT_CONSUMER_PROJECTION_FRESHNESS_POLICIES = (

    ResearchWorkspaceConsumerProjectionFreshnessPolicy(

        source_name="workspace.recent_activity",

        fresh_for_ms=(

            5

            * 60

            * 1000
        ),

        usable_for_ms=(

            60

            * 60

            * 1000
        ),
    ),
)


class ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry:
    """
    Owns the authoritative freshness
    policy for each freshness-aware
    source. Distinct from the execution
    policy registry (Commit #9) — a
    source's staleness tolerance does not
    change with which operation reads it.
    """

    def __init__(

        self,

        policies=None,

    ):

        policies = (

            policies

            or DEFAULT_CONSUMER_PROJECTION_FRESHNESS_POLICIES
        )

        seen_source_names = set()

        for policy in policies:

            if (

                policy.source_name

                in seen_source_names
            ):

                raise ValueError(

                    "Duplicate freshness "
                    "policy source name: "
                    f"{policy.source_name}"
                )

            seen_source_names.add(
                policy.source_name
            )

        self._policies = {

            policy.source_name:
                policy

            for policy

            in policies
        }

    def get_policy(

        self,

        source_name,

    ):

        return (

            self._policies
            .get(
                source_name
            )
        )

    def list_policies(self):

        return list(

            self._policies
            .values()
        )
