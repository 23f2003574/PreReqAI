from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentCapabilityExecution
from .store import ExecutionStore


class JsonExecutionStore(ExecutionStore):
    """Persists durable capability execution records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, execution: LLMAgentCapabilityExecution) -> LLMAgentCapabilityExecution:
        executions = self.file.read()
        executions[execution.execution_id] = execution.to_dict()
        self.file.write(executions)
        return execution

    def get(self, execution_id: str):
        executions = self.file.read()
        data = executions.get(execution_id)
        return None if data is None else LLMAgentCapabilityExecution.from_dict(data)

    def list_for_agent(self, agent_id: str) -> list:
        executions = self.file.read()
        matching = [
            LLMAgentCapabilityExecution.from_dict(data)
            for data in executions.values()
            if data.get("agent_id") == agent_id
        ]
        return sorted(matching, key=lambda item: item.started_at)

    def list_for_capability(self, capability_id: str) -> list:
        executions = self.file.read()
        matching = [
            LLMAgentCapabilityExecution.from_dict(data)
            for data in executions.values()
            if data.get("capability_id") == capability_id
        ]
        return sorted(matching, key=lambda item: item.started_at)
