from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicyTemplate, LLMAgentPolicyTemplateInstantiation
from .store import LLMAgentPolicyTemplateInstantiationStore, LLMAgentPolicyTemplateStore


class JsonLLMAgentPolicyTemplateStore(LLMAgentPolicyTemplateStore):
    """Persists durable LLM agent policy templates to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, template: LLMAgentPolicyTemplate) -> LLMAgentPolicyTemplate:
        template.updated_at = datetime.now(timezone.utc)

        templates = self.file.read()
        templates[template.template_id] = template.to_dict()
        self.file.write(templates)

        return deepcopy(template)

    def get(self, template_id: str):
        templates = self.file.read()
        data = templates.get(template_id)
        return None if data is None else LLMAgentPolicyTemplate.from_dict(data)

    def list(self, status: str = None):
        templates = self.file.read()
        matching = [
            LLMAgentPolicyTemplate.from_dict(data)
            for data in templates.values()
            if status is None or data.get("status") == status
        ]
        return sorted(matching, key=lambda item: item.created_at)


class JsonLLMAgentPolicyTemplateInstantiationStore(LLMAgentPolicyTemplateInstantiationStore):
    """Persists durable LLM agent policy template instantiation records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, instantiation: LLMAgentPolicyTemplateInstantiation) -> LLMAgentPolicyTemplateInstantiation:
        instantiations = self.file.read()
        instantiations[instantiation.policy_id] = instantiation.to_dict()
        self.file.write(instantiations)
        return deepcopy(instantiation)

    def get_for_policy(self, policy_id: str):
        instantiations = self.file.read()
        data = instantiations.get(policy_id)
        return None if data is None else LLMAgentPolicyTemplateInstantiation.from_dict(data)

    def list_for_template(self, template_id: str):
        instantiations = self.file.read()
        matching = [
            LLMAgentPolicyTemplateInstantiation.from_dict(data)
            for data in instantiations.values()
            if data.get("template_id") == template_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
