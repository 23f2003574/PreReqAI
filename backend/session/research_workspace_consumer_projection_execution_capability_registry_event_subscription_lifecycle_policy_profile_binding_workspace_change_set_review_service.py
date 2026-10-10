from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

_DECISION_VERBS = {
    "approved": "approve",
    "rejected": "reject",
}

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_approval_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService:
    """
    Gates consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace change
    sets behind a reviewer approval workflow, so a change set must
    collect enough reviewer approval, per an approval policy, before
    it is considered ready to apply.

    The service's responsibility is review submission, approval,
    rejection, and readiness evaluation, not change set creation,
    operation staging, previewing, applying, or discarding. It does
    NOT create change sets, stage or remove operations, preview or
    apply a change set, mutate a workspace, persist reviews
    externally, log, or publish events. It operates over a change set
    service supplied at construction time to resolve a change set's
    current lifecycle status; it never calls apply, discard, or any
    other mutating method on it.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Reviewable-while-open: A review may only be submitted, approved,
      or rejected while its change set is open; once a change set is
      applied or discarded, its reviews are frozen
    - Duplicate-free per round: A reviewer may not have more than one
      pending or approved review outstanding on the same change set
      at a time
    - Resubmittable: A reviewer whose review was rejected may submit a
      new review, which supersedes their rejected one for readiness
      purposes without erasing it from history
    - History-retaining: Every review ever submitted for a change set
      remains retrievable, including superseded ones
    - Policy-driven: Readiness is determined entirely by the approval
      policy supplied at construction time, evaluated against each
      reviewer's current (most recently submitted) review
    """

    def __init__(
        self,
        change_set_service,
        approval_policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy,
    ):
        """
        Args:
            change_set_service: The service used to resolve a change
                set's current lifecycle status. Any object exposing
                `find(change_set_id)`, returning an object with a
                `status` attribute, is accepted
            approval_policy: The policy used to evaluate whether a
                change set's current reviews satisfy readiness

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If change_set_service is None, approval_policy is
                None, or approval_policy is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy
        """

        if change_set_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot initialize change set review service with a None change set service."
            )

        if approval_policy is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot initialize change set review service with a None approval policy."
            )

        if not isinstance(
            approval_policy,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                "Cannot initialize change set review service: approval_policy must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy."
            )

        self._change_set_service = change_set_service
        self._approval_policy = approval_policy
        self._reviews = {}
        self._review_order_by_change_set = {}
        self._lock = RLock()

    def submit(
        self,
        change_set_id: str,
        reviewer: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
        """
        Submit a new, pending review for a reviewer on a change set.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If change_set_id or reviewer is None or blank, no
                change set is registered under change_set_id, the
                change set is not open, or the reviewer already has a
                pending or approved review on the change set
        """

        self._validate_id(change_set_id, "change set ID")
        self._validate_id(reviewer, "reviewer")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)
            self._require_open(change_set, "submit a review for")

            latest = self._latest_review_for_reviewer(change_set_id, reviewer)

            if latest is not None and latest.status in (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                    f"Cannot submit a review: reviewer {reviewer!r} already has a {latest.status.value} review "
                    f"for change set ID {change_set_id!r}."
                )

            review = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview(
                review_id=str(uuid4()),
                change_set_id=change_set_id,
                reviewer=reviewer,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING,
                comments=None,
                reviewed_at=None,
            )

            self._reviews[review.review_id] = review
            self._review_order_by_change_set.setdefault(change_set_id, []).append(review.review_id)

            return review

    def approve(
        self,
        review_id: str,
        comments: str | None = None,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
        """
        Approve a pending review.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If review_id is None or blank, no review is
                registered under it, its change set is no longer
                open, or the review is not pending
        """

        return self._decide(
            review_id,
            comments,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED,
        )

    def reject(
        self,
        review_id: str,
        comments: str | None = None,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
        """
        Reject a pending review.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If review_id is None or blank, no review is
                registered under it, its change set is no longer
                open, or the review is not pending
        """

        return self._decide(
            review_id,
            comments,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.REJECTED,
        )

    def status(self, change_set_id: str):
        """
        Compute a change set's current aggregate review status from
        each reviewer's current (most recently submitted) review,
        evaluated against the approval policy.

        Returns:
            None if no review has ever been submitted for the change
            set; REJECTED if any current review is rejected; APPROVED
            if the current reviews satisfy the approval policy;
            PENDING otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If change_set_id is None or blank, or no change set is
                registered under it
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            self._resolve_change_set(change_set_id)

            current_reviews = self._current_reviews(change_set_id)

            if not current_reviews:
                return None

            if any(
                review.status
                == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.REJECTED
                for review in current_reviews
            ):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.REJECTED

            approvals = sum(
                1
                for review in current_reviews
                if review.status
                == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED
            )

            if self._approval_policy.require_unanimous:
                if approvals == len(current_reviews) and approvals >= self._approval_policy.minimum_approvals:
                    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED

                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING

            if approvals >= self._approval_policy.minimum_approvals:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING

    def can_apply(self, change_set_id: str) -> bool:
        """
        Check whether a change set is open and its current reviews
        satisfy the approval policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If change_set_id is None or blank, or no change set is
                registered under it
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                return False

            return (
                self.status(change_set_id)
                == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED
            )

    def history(self, change_set_id: str) -> tuple:
        """
        List every review ever submitted for a change set, including
        superseded ones, in submission order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If change_set_id is None or blank
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            review_ids = self._review_order_by_change_set.get(change_set_id, ())

            return tuple(self._reviews[review_id] for review_id in review_ids)

    def find(self, review_id: str):
        """
        Find the review registered under a review ID.

        Returns:
            The matching review, or None if no review is registered
            under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError:
                If review_id is None or blank
        """

        self._validate_id(review_id, "review ID")

        with self._lock:
            return self._reviews.get(review_id)

    def _decide(
        self,
        review_id: str,
        comments: str | None,
        outcome: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
        self._validate_id(review_id, "review ID")

        with self._lock:
            review = self._resolve_review(review_id)
            change_set = self._resolve_change_set(review.change_set_id)

            verb = _DECISION_VERBS[outcome.value]

            self._require_open(change_set, f"{verb} a review for")

            if review.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.PENDING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                    f"Cannot {verb} review ID {review_id!r}: it is {review.status.value}, not pending."
                )

            decided = replace(
                review,
                status=outcome,
                comments=comments,
                reviewed_at=datetime.now(timezone.utc),
            )

            self._reviews[review_id] = decided

            return decided

    def _current_reviews(self, change_set_id: str) -> tuple:
        review_ids = self._review_order_by_change_set.get(change_set_id, ())

        latest_by_reviewer = {}
        reviewer_order = []

        for review_id in review_ids:
            review = self._reviews[review_id]

            if review.reviewer not in latest_by_reviewer:
                reviewer_order.append(review.reviewer)

            latest_by_reviewer[review.reviewer] = review

        return tuple(latest_by_reviewer[reviewer] for reviewer in reviewer_order)

    def _latest_review_for_reviewer(self, change_set_id: str, reviewer: str):
        review_ids = self._review_order_by_change_set.get(change_set_id, ())

        latest = None

        for review_id in review_ids:
            review = self._reviews[review_id]

            if review.reviewer == reviewer:
                latest = review

        return latest

    def _resolve_review(
        self,
        review_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReview:
        review = self._reviews.get(review_id)

        if review is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                f"Cannot operate on a review: no review is registered under review ID {review_id!r}."
            )

        return review

    def _resolve_change_set(self, change_set_id: str):
        change_set = self._change_set_service.find(change_set_id)

        if change_set is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                f"Cannot operate on a review: no change set is registered under change set ID {change_set_id!r}."
            )

        return change_set

    def _require_open(self, change_set, action: str) -> None:
        if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                f"Cannot {action} change set ID {change_set.change_set_id!r}: it is {change_set.status.value}, not open."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewError(
                f"Cannot operate on a review with an empty or blank {label}."
            )
