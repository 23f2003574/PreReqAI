from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentRiskProfileVersion


class RiskProfileVersionStore(ABC):
    """Persistence operations for immutable, append-only risk profile
    versions.

    Mirrors the exact save/get/list_for_-- shape every other
    audit/history-adjacent store in this repository already uses (e.g.
    backend.agent_policy_history.LLMAgentPolicyHistoryStore). There is
    no update() or delete(): a version, once saved, is never rewritten
    or removed -- LLMAgentRiskProfileVersionService.create_version()
    only ever appends a new one, or returns an existing one unchanged.
    """

    @abstractmethod
    def save(self, version: LLMAgentRiskProfileVersion) -> LLMAgentRiskProfileVersion:
        ...

    @abstractmethod
    def get(self, version_id: str) -> Optional[LLMAgentRiskProfileVersion]:
        ...

    @abstractmethod
    def list_for_profile(self, profile_id: str) -> list:
        ...
