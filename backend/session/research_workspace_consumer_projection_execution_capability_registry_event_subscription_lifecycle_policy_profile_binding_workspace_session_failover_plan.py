from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_failover_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan:
    """
    Immutable, reusable plan naming which execution worker a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session
    should run on, and which backup workers to fail over to, in
    order, if that worker becomes unavailable before execution
    begins.

    The plan is a value object only. It performs no failover.
    Registering plans and failing sessions over between workers is
    the responsibility of a session scheduling failover service.

    Attributes:
        plan_id: The plan's unique identifier
        session_id: The identifier of the execution session this plan
            applies to
        primary_worker: The execution worker the session is placed on
            while it is available
        backup_workers: The execution workers to fail over to, in the
            order they should be tried; must be non-empty, contain no
            duplicates, and never repeat primary_worker
    """

    plan_id: str

    session_id: str

    primary_worker: str

    backup_workers: tuple[
        str,
        ...,
    ]

    def __post_init__(self):
        if self.plan_id is None or not self.plan_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan with an empty or blank plan ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan with an empty or blank session ID."
            )

        if self.primary_worker is None or not self.primary_worker.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan with an empty or blank primary_worker."
            )

        if (
            not isinstance(self.backup_workers, tuple)
            or not self.backup_workers
            or any(
                worker_id is None or not isinstance(worker_id, str) or not worker_id.strip()
                for worker_id in self.backup_workers
            )
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan without a non-empty tuple of non-blank backup_workers."
            )

        if len(set(self.backup_workers)) != len(self.backup_workers):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan with duplicate backup_workers."
            )

        if self.primary_worker in self.backup_workers:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot build a session failover plan whose backup_workers repeats primary_worker."
            )
