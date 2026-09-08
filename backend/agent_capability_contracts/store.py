from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentCapabilityContract


class ContractStore(ABC):
    """Persistence operations for durable, immutable LLM agent capability
    contracts, keyed by (capability_id, version).

    Mirrors backend.agent_risk_profile.RiskProfileStore's own
    save/get/list_for_scope shape, generalized from "one scope, many
    profiles" to "one capability_id, many versioned contracts" --
    list_for_capability() plays list_for_scope()'s role. There is no
    update() or delete(): a contract is immutable once registered (Rule:
    "contract changes must not silently invalidate existing versions"),
    so the only way to change what a capability's contract says is to
    save() a new version's contract, which never touches an
    already-stored one.
    """

    @abstractmethod
    def save(self, contract: LLMAgentCapabilityContract) -> LLMAgentCapabilityContract:
        ...

    @abstractmethod
    def get(self, capability_id: str, version: str) -> Optional[LLMAgentCapabilityContract]:
        ...

    @abstractmethod
    def list_for_capability(self, capability_id: str) -> list:
        ...
