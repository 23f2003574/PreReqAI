from abc import ABC, abstractmethod
from typing import Optional

from .models import ReviewItem


class ReviewQueueStore(ABC):
    """Persistence operations for durable ReviewItem records.

    Mirrors backend.agent_policy_risk_approval.ApprovalRequirementStore's
    own save/get/list_for_scope/current_for_context shape -- the same
    "one live pointer per identity" convention every store in this
    series has used since Commit #5, here keyed by the Commit #5
    request_id a review item was enqueued from (see Rules: "Queue
    operations must be idempotent where applicable" -- at most one
    review item is ever current for a given approval_request_id).

    Only an InMemory implementation is provided, for the same reason
    every other store in this sub-series gives: a durable ReviewItem
    embeds a full Commit #4 RiskDecision, not designed for JSON
    round-tripping.
    """

    @abstractmethod
    def save(self, item: ReviewItem) -> ReviewItem:
        ...

    @abstractmethod
    def get(self, item_id: str) -> Optional[ReviewItem]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...

    @abstractmethod
    def current_for_request(self, approval_request_id: str) -> Optional[str]:
        """The item_id of the current review item for
        approval_request_id, or None if none has ever been enqueued for
        it."""
        ...

    @abstractmethod
    def set_current_for_request(self, approval_request_id: str, item_id: str) -> None:
        ...
