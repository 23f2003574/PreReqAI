from copy import deepcopy

from .models import ApprovalRequirement
from .store import ApprovalRequirementStore


class InMemoryApprovalRequirementStore(ApprovalRequirementStore):
    """Stores durable ApprovalRequirement records in memory, for
    development and testing."""

    def __init__(self):
        self._requirements: dict[str, ApprovalRequirement] = {}
        self._current_by_context: dict[str, str] = {}

    def save(self, requirement: ApprovalRequirement) -> ApprovalRequirement:
        stored = deepcopy(requirement)
        self._requirements[requirement.request_id] = stored
        return deepcopy(stored)

    def get(self, request_id: str):
        requirement = self._requirements.get(request_id)
        return deepcopy(requirement) if requirement is not None else None

    def list_for_scope(self, scope_id: str) -> list:
        matching = [
            requirement
            for requirement in self._requirements.values()
            if requirement.scope_id == scope_id
        ]
        return [deepcopy(requirement) for requirement in sorted(matching, key=lambda item: item.created_at)]

    def current_for_context(self, context_key: str):
        return self._current_by_context.get(context_key)

    def set_current_for_context(self, context_key: str, request_id: str) -> None:
        self._current_by_context[context_key] = request_id
