from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentStrategyDecision
from .store import LLMAgentStrategyDecisionStore


class JsonLLMAgentStrategyDecisionStore(LLMAgentStrategyDecisionStore):
    """Persists durable LLM agent strategy decision audit records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, decision: LLMAgentStrategyDecision) -> LLMAgentStrategyDecision:
        decisions = self.file.read()
        decisions[decision.decision_id] = decision.to_dict()
        self.file.write(decisions)
        return decision

    def get(self, decision_id: str):
        decisions = self.file.read()
        data = decisions.get(decision_id)
        return None if data is None else LLMAgentStrategyDecision.from_dict(data)

    def list_for_strategy(self, strategy_id: str):
        decisions = self.file.read()
        matching = [
            LLMAgentStrategyDecision.from_dict(data)
            for data in decisions.values()
            if data.get("strategy_id") == strategy_id
        ]
        return sorted(matching, key=lambda item: item.created_at)

    def list_for_execution(self, execution_or_task_id: str):
        decisions = self.file.read()
        matching = [
            LLMAgentStrategyDecision.from_dict(data)
            for data in decisions.values()
            if data.get("execution_or_task_id") == execution_or_task_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
