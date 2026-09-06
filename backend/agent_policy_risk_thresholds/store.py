from abc import ABC, abstractmethod
from typing import Optional

from .models import RiskThresholds


class RiskThresholdsStore(ABC):
    """Persistence operations for one scope's current RiskThresholds.

    Mirrors backend.agent_policy_engine.LLMAgentPolicyStore's own
    save/get shape -- the same existing configuration-persistence
    pattern this series has used from Commit #1 onward -- rather than
    introducing a new configuration framework. Unlike LLMAgentPolicy
    (which keeps every version via list_for_scope()), a scope has
    exactly one current RiskThresholds record: save() always replaces
    whatever was previously stored for that scope_id.
    """

    @abstractmethod
    def save(self, thresholds: RiskThresholds) -> RiskThresholds:
        ...

    @abstractmethod
    def get(self, scope_id: str) -> Optional[RiskThresholds]:
        ...
