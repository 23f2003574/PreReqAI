from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentCapability
from .store import CapabilityStore


class InMemoryCapabilityStore(CapabilityStore):
    """Stores durable LLM agent capability records in memory, for
    development and testing."""

    def __init__(self):
        self._capabilities: dict[str, LLMAgentCapability] = {}

    def save(self, capability: LLMAgentCapability) -> LLMAgentCapability:
        capability.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(capability)
        self._capabilities[capability.capability_id] = stored
        return deepcopy(stored)

    def get(self, capability_id: str):
        capability = self._capabilities.get(capability_id)
        return deepcopy(capability) if capability is not None else None

    def list(self, status: str = None):
        matching = [
            capability
            for capability in self._capabilities.values()
            if status is None or capability.status == status
        ]
        return [deepcopy(capability) for capability in sorted(matching, key=lambda item: item.created_at)]
