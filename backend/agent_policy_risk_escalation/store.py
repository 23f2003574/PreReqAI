from abc import ABC, abstractmethod
from typing import Optional

from .models import Escalation


class EscalationStore(ABC):
    """Persistence operations for durable Escalation records.

    Mirrors backend.agent_policy_risk_approval.ApprovalRequirementStore's
    own save/get/list_for_scope shape -- "the repository's existing
    configuration/persistence pattern" (see Rules: "Reuse existing ...
    workflow persistence where available") -- plus
    active_for_request()/set_active_for_request(), the same
    "one live pointer per identity" addition
    ApprovalRequirementStore made for its own context_key, here keyed by
    the Commit #5 request_id an escalation was raised against instead
    (see Rules: "Only review/approval-required actions can escalate" --
    at most one escalation is ever active for a given request_id at a
    time).

    Only an InMemory implementation is provided, for the exact reason
    ApprovalRequirementStore's own docstring already gives: an
    Escalation embeds a full Commit #4 RiskDecision, not designed for
    JSON round-tripping, and reshaping it into a compact, JSON-friendly
    audit record is a separate concern left to a later commit.
    """

    @abstractmethod
    def save(self, escalation: Escalation) -> Escalation:
        ...

    @abstractmethod
    def get(self, escalation_id: str) -> Optional[Escalation]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...

    @abstractmethod
    def active_for_request(self, request_id: str) -> Optional[str]:
        """The escalation_id of the currently-active (non-terminal)
        escalation for request_id, or None if it has none."""
        ...

    @abstractmethod
    def set_active_for_request(self, request_id: str, escalation_id: Optional[str]) -> None:
        """Set (or, with None, clear) the active escalation_id for
        request_id."""
        ...
