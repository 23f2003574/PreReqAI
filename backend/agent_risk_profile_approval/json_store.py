from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import RiskProfileApproval
from .store import RiskProfileApprovalStore


class JsonRiskProfileApprovalStore(RiskProfileApprovalStore):
    """Persists risk profile approval records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, approval: RiskProfileApproval) -> RiskProfileApproval:
        approvals = self.file.read()
        approvals[approval.approval_id] = approval.to_dict()
        self.file.write(approvals)
        return approval

    def get(self, approval_id: str):
        approvals = self.file.read()
        data = approvals.get(approval_id)
        return None if data is None else self._from_dict(data)

    def list_for_key(self, profile_id: str, version: int, scope_id: str):
        approvals = self.file.read()
        matching = [
            self._from_dict(data)
            for data in approvals.values()
            if data.get("profile_id") == profile_id
            and data.get("version") == version
            and data.get("scope_id") == scope_id
        ]
        return sorted(matching, key=lambda item: item.created_at)

    @staticmethod
    def _from_dict(data: dict) -> RiskProfileApproval:
        from datetime import datetime

        payload = dict(data)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        if isinstance(payload.get("resolved_at"), str):
            payload["resolved_at"] = datetime.fromisoformat(payload["resolved_at"])
        return RiskProfileApproval(**payload)
