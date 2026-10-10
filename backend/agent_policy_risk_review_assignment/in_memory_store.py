from copy import deepcopy
from typing import Optional

from .models import Assignment
from .store import AssignmentStore


class InMemoryAssignmentStore(AssignmentStore):
    """Stores durable Assignment records in memory, for development and
    testing."""

    def __init__(self):
        self._assignments: dict[str, Assignment] = {}
        self._active_by_item: dict[str, str] = {}

    def save(self, assignment: Assignment) -> Assignment:
        stored = deepcopy(assignment)
        self._assignments[assignment.assignment_id] = stored
        return deepcopy(stored)

    def get(self, assignment_id: str):
        assignment = self._assignments.get(assignment_id)
        return deepcopy(assignment) if assignment is not None else None

    def list_for_item(self, item_id: str) -> list:
        matching = [a for a in self._assignments.values() if a.item_id == item_id]
        return [deepcopy(a) for a in sorted(matching, key=lambda entry: entry.assigned_at)]

    def list_for_reviewer(self, reviewer: str, scope_id: str) -> list:
        matching = [
            a for a in self._assignments.values() if a.reviewer == reviewer and a.scope_id == scope_id
        ]
        return [deepcopy(a) for a in sorted(matching, key=lambda entry: entry.assigned_at)]

    def active_for_item(self, item_id: str):
        return self._active_by_item.get(item_id)

    def set_active_for_item(self, item_id: str, assignment_id: Optional[str]) -> None:
        if assignment_id is None:
            self._active_by_item.pop(item_id, None)
        else:
            self._active_by_item[item_id] = assignment_id
