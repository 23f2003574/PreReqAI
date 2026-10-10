from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import RiskThresholds
from .store import RiskThresholdsStore


class JsonRiskThresholdsStore(RiskThresholdsStore):
    """Persists durable per-scope risk thresholds to a JSON file, the
    same backend.storage.AtomicJsonFile-backed persistence
    backend.agent_policy_engine.JsonLLMAgentPolicyStore already uses."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, thresholds: RiskThresholds) -> RiskThresholds:
        all_thresholds = self.file.read()
        all_thresholds[thresholds.scope_id] = thresholds.to_dict()
        self.file.write(all_thresholds)
        return thresholds

    def get(self, scope_id: str):
        all_thresholds = self.file.read()
        data = all_thresholds.get(scope_id)
        return None if data is None else RiskThresholds.from_dict(data)
