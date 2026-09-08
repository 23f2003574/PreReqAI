from copy import deepcopy

from .models import LLMAgentCapabilityExecution
from .store import ExecutionStore


class InMemoryExecutionStore(ExecutionStore):
    """Stores durable capability execution records in memory, for
    development and testing."""

    def __init__(self):
        self._executions: dict[str, LLMAgentCapabilityExecution] = {}

    def save(self, execution: LLMAgentCapabilityExecution) -> LLMAgentCapabilityExecution:
        stored = deepcopy(execution)
        self._executions[execution.execution_id] = stored
        return deepcopy(stored)

    def get(self, execution_id: str):
        execution = self._executions.get(execution_id)
        return deepcopy(execution) if execution is not None else None

    def list_for_agent(self, agent_id: str) -> list:
        matching = [execution for execution in self._executions.values() if execution.agent_id == agent_id]
        return [deepcopy(execution) for execution in sorted(matching, key=lambda item: item.started_at)]

    def list_for_capability(self, capability_id: str) -> list:
        matching = [
            execution for execution in self._executions.values() if execution.capability_id == capability_id
        ]
        return [deepcopy(execution) for execution in sorted(matching, key=lambda item: item.started_at)]
