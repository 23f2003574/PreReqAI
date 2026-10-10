from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentCapabilityContract
from .store import ContractStore


class JsonContractStore(ContractStore):
    """Persists durable LLM agent capability contracts to a JSON file,
    nested by capability_id then version."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, contract: LLMAgentCapabilityContract) -> LLMAgentCapabilityContract:
        contracts = self.file.read()
        contracts.setdefault(contract.capability_id, {})[contract.version] = contract.to_dict()
        self.file.write(contracts)
        return deepcopy(contract)

    def get(self, capability_id: str, version: str):
        contracts = self.file.read()
        data = contracts.get(capability_id, {}).get(version)
        return None if data is None else LLMAgentCapabilityContract.from_dict(data)

    def list_for_capability(self, capability_id: str):
        contracts = self.file.read()
        loaded = [
            LLMAgentCapabilityContract.from_dict(data)
            for data in contracts.get(capability_id, {}).values()
        ]
        return sorted(loaded, key=lambda item: item.created_at)
