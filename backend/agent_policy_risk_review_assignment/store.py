from abc import ABC, abstractmethod
from typing import Optional

from .models import Assignment


class AssignmentStore(ABC):
    """Persistence operations for durable Assignment records.

    Mirrors the same save/get/list-plus-"one live pointer per identity"
    shape every store in this series has used since Commit #5 -- here
    keyed by the Commit #8 item_id an assignment governs (see Rules:
    "Only one active reviewer owns an item"), plus list_for_reviewer()
    for reviewer-scoped listing (see Rules: "reviewer filtering").

    Unlike every other store in this sub-series, Assignment does not
    embed a Commit #4 RiskDecision directly -- it only embeds a Commit
    #8 ReviewItem in its own provenance dict -- but this is still kept
    InMemory-only for consistency with the rest of the sub-series and
    because a durable, JSON-friendly reshaping of an embedded ReviewItem
    is the same deferred concern already documented on
    ApprovalRequirementStore/EscalationStore/ReviewQueueStore.
    """

    @abstractmethod
    def save(self, assignment: Assignment) -> Assignment:
        ...

    @abstractmethod
    def get(self, assignment_id: str) -> Optional[Assignment]:
        ...

    @abstractmethod
    def list_for_item(self, item_id: str) -> list:
        """Every assignment ever made for item_id, oldest first --
        active and revoked alike (see Rules: "Reassignment preserves
        history")."""
        ...

    @abstractmethod
    def list_for_reviewer(self, reviewer: str, scope_id: str) -> list:
        """Every assignment ever made to reviewer within scope_id,
        oldest first -- active and revoked alike."""
        ...

    @abstractmethod
    def active_for_item(self, item_id: str) -> Optional[str]:
        """The assignment_id of item_id's current ACTIVE assignment, or
        None if it has none."""
        ...

    @abstractmethod
    def set_active_for_item(self, item_id: str, assignment_id: Optional[str]) -> None:
        """Set (or, with None, clear) the active assignment_id for
        item_id."""
        ...
