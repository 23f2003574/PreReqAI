from typing import Mapping

from .research_workspace_consumer_projection_fingerprint_errors import (
    ResearchWorkspaceProjectionFingerprintPolicyNotFoundError,
)

from .research_workspace_consumer_projection_fingerprint_policy import (
    ResearchWorkspaceConsumerProjectionFingerprintPolicy,
)


class ResearchWorkspaceConsumerProjectionFingerprintPolicyRegistry:
    """
    Registry for projection-specific fingerprinting policies.

    Policies are looked up by projection name.
    All policies must be registered explicitly;
    there is no dynamic discovery or fallback.

    Attempting to fingerprint an unregistered projection
    raises a clear error rather than silently using
    a generic hash.
    """

    def __init__(
        self,
    ):
        self._policies: Mapping[
            str,
            ResearchWorkspaceConsumerProjectionFingerprintPolicy,
        ] = {}

    def register_policy(
        self,
        policy: (
            ResearchWorkspaceConsumerProjectionFingerprintPolicy
        ),
    ) -> None:
        """
        Registers a fingerprinting policy.

        Arguments:
            policy: The policy to register
        """

        self._policies[policy.projection_name] = policy

    def get_policy(
        self,
        projection_name: str,
    ) -> ResearchWorkspaceConsumerProjectionFingerprintPolicy:
        """
        Retrieves a registered policy.

        Arguments:
            projection_name: The projection identifier

        Returns:
            The registered fingerprinting policy

        Raises:
            ResearchWorkspaceProjectionFingerprintPolicyNotFoundError:
                If no policy is registered for this projection
        """

        policy = self._policies.get(projection_name)

        if policy is None:
            raise ResearchWorkspaceProjectionFingerprintPolicyNotFoundError(
                f"No fingerprinting policy found for projection: {projection_name}"
            )

        return policy
