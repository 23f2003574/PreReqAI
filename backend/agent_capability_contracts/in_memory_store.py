from copy import deepcopy

from .models import LLMAgentCapabilityContract
from .store import ContractStore


class InMemoryContractStore(ContractStore):
    """Stores durable LLM agent capability contracts in memory, for
    development and testing."""

    def __init__(self):
        self._contracts: dict[str, dict[str, LLMAgentCapabilityContract]] = {}

    def save(self, contract: LLMAgentCapabilityContract) -> LLMAgentCapabilityContract:
        stored = deepcopy(contract)
        self._contracts.setdefault(contract.capability_id, {})[contract.version] = stored
        return deepcopy(stored)

    def get(self, capability_id: str, version: str):
        contract = self._contracts.get(capability_id, {}).get(version)
        return deepcopy(contract) if contract is not None else None

    def list_for_capability(self, capability_id: str):
        contracts = self._contracts.get(capability_id, {}).values()
        return [deepcopy(contract) for contract in sorted(contracts, key=lambda item: item.created_at)]
