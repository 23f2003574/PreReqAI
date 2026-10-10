from copy import deepcopy

from .models import RiskThresholds
from .store import RiskThresholdsStore


class InMemoryRiskThresholdsStore(RiskThresholdsStore):
    """Stores durable per-scope risk thresholds in memory, for
    development and testing."""

    def __init__(self):
        self._thresholds: dict[str, RiskThresholds] = {}

    def save(self, thresholds: RiskThresholds) -> RiskThresholds:
        stored = deepcopy(thresholds)
        self._thresholds[thresholds.scope_id] = stored
        return deepcopy(stored)

    def get(self, scope_id: str):
        thresholds = self._thresholds.get(scope_id)
        return deepcopy(thresholds) if thresholds is not None else None
