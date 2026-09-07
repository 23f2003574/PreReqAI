from copy import deepcopy

from .models import RiskProfileApproval
from .store import RiskProfileApprovalStore


class InMemoryRiskProfileApprovalStore(RiskProfileApprovalStore):
    """Stores risk profile approval records in memory, for development
    and testing."""

    def __init__(self):
        self._approvals: dict[str, RiskProfileApproval] = {}

    def save(self, approval: RiskProfileApproval) -> RiskProfileApproval:
        stored = deepcopy(approval)
        self._approvals[approval.approval_id] = stored
        return deepcopy(stored)

    def get(self, approval_id: str):
        approval = self._approvals.get(approval_id)
        return deepcopy(approval) if approval is not None else None

    def list_for_key(self, profile_id: str, version: int, scope_id: str):
        matching = [
            approval
            for approval in self._approvals.values()
            if approval.profile_id == profile_id and approval.version == version and approval.scope_id == scope_id
        ]
        return [deepcopy(approval) for approval in sorted(matching, key=lambda item: item.created_at)]
