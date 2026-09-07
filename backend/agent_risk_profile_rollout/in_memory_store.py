from copy import deepcopy

from .models import RiskProfileRollout
from .store import RiskProfileRolloutStore


class InMemoryRiskProfileRolloutStore(RiskProfileRolloutStore):
    """Stores risk profile rollout records in memory, for development
    and testing."""

    def __init__(self):
        self._rollouts: dict[str, RiskProfileRollout] = {}

    def save(self, rollout: RiskProfileRollout) -> RiskProfileRollout:
        stored = deepcopy(rollout)
        self._rollouts[rollout.rollout_id] = stored
        return deepcopy(stored)

    def get(self, rollout_id: str):
        rollout = self._rollouts.get(rollout_id)
        return deepcopy(rollout) if rollout is not None else None

    def list_for_profile_scope(self, profile_id: str, scope_id: str):
        matching = [
            rollout
            for rollout in self._rollouts.values()
            if rollout.profile_id == profile_id and rollout.scope_id == scope_id
        ]
        return [deepcopy(rollout) for rollout in sorted(matching, key=lambda item: item.started_at)]
