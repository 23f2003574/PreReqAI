from copy import deepcopy
from typing import Optional

from .models import Escalation
from .store import EscalationStore


class InMemoryEscalationStore(EscalationStore):
    """Stores durable Escalation records in memory, for development and
    testing."""

    def __init__(self):
        self._escalations: dict[str, Escalation] = {}
        self._active_by_request: dict[str, str] = {}

    def save(self, escalation: Escalation) -> Escalation:
        stored = deepcopy(escalation)
        self._escalations[escalation.escalation_id] = stored
        return deepcopy(stored)

    def get(self, escalation_id: str):
        escalation = self._escalations.get(escalation_id)
        return deepcopy(escalation) if escalation is not None else None

    def list_for_scope(self, scope_id: str) -> list:
        matching = [
            escalation for escalation in self._escalations.values() if escalation.scope_id == scope_id
        ]
        return [deepcopy(escalation) for escalation in sorted(matching, key=lambda item: item.created_at)]

    def active_for_request(self, request_id: str):
        return self._active_by_request.get(request_id)

    def set_active_for_request(self, request_id: str, escalation_id: Optional[str]) -> None:
        if escalation_id is None:
            self._active_by_request.pop(request_id, None)
        else:
            self._active_by_request[request_id] = escalation_id
