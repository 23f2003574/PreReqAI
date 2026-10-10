from copy import deepcopy

from .models import ReviewItem
from .store import ReviewQueueStore


class InMemoryReviewQueueStore(ReviewQueueStore):
    """Stores durable ReviewItem records in memory, for development and
    testing."""

    def __init__(self):
        self._items: dict[str, ReviewItem] = {}
        self._current_by_request: dict[str, str] = {}

    def save(self, item: ReviewItem) -> ReviewItem:
        stored = deepcopy(item)
        self._items[item.item_id] = stored
        return deepcopy(stored)

    def get(self, item_id: str):
        item = self._items.get(item_id)
        return deepcopy(item) if item is not None else None

    def list_for_scope(self, scope_id: str) -> list:
        matching = [item for item in self._items.values() if item.scope_id == scope_id]
        return [deepcopy(item) for item in sorted(matching, key=lambda entry: entry.created_at)]

    def current_for_request(self, approval_request_id: str):
        return self._current_by_request.get(approval_request_id)

    def set_current_for_request(self, approval_request_id: str, item_id: str) -> None:
        self._current_by_request[approval_request_id] = item_id
