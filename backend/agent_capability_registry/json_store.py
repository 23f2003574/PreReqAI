from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentCapability
from .store import CapabilityStore


class JsonCapabilityStore(CapabilityStore):
    """Persists durable LLM agent capability records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, capability: LLMAgentCapability) -> LLMAgentCapability:
        capability.updated_at = datetime.now(timezone.utc)

        capabilities = self.file.read()
        capabilities[capability.capability_id] = capability.to_dict()
        self.file.write(capabilities)

        return deepcopy(capability)

    def get(self, capability_id: str):
        capabilities = self.file.read()
        data = capabilities.get(capability_id)
        return None if data is None else LLMAgentCapability.from_dict(data)

    def list(self, status: str = None):
        capabilities = self.file.read()
        matching = [
            LLMAgentCapability.from_dict(data)
            for data in capabilities.values()
            if status is None or data.get("status") == status
        ]
        return sorted(matching, key=lambda item: item.created_at)
