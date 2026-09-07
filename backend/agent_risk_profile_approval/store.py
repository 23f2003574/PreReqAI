from abc import ABC, abstractmethod
from typing import Optional

from .models import RiskProfileApproval


class RiskProfileApprovalStore(ABC):
    """Persistence operations for immutable risk profile approval
    records.

    Mirrors the exact save/get/list_for_-- shape every other
    audit/history-adjacent store in this repository already uses.
    There is deliberately no update() or delete(): an approval record,
    once saved, is only ever replaced by a fresh dataclasses.replace()
    result written back via save() -- "preserve historical approval
    decisions; do not overwrite them" means every save() call persists
    a *new* record under its own approval_id, never mutating one
    already stored under a different id.
    """

    @abstractmethod
    def save(self, approval: RiskProfileApproval) -> RiskProfileApproval:
        ...

    @abstractmethod
    def get(self, approval_id: str) -> Optional[RiskProfileApproval]:
        ...

    @abstractmethod
    def list_for_key(self, profile_id: str, version: int, scope_id: str) -> list:
        ...
