from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentPolicyTemplate, LLMAgentPolicyTemplateInstantiation
from .store import LLMAgentPolicyTemplateInstantiationStore, LLMAgentPolicyTemplateStore


class InMemoryLLMAgentPolicyTemplateStore(LLMAgentPolicyTemplateStore):
    """Stores durable LLM agent policy templates in memory, for
    development and testing."""

    def __init__(self):
        self._templates: dict[str, LLMAgentPolicyTemplate] = {}

    def save(self, template: LLMAgentPolicyTemplate) -> LLMAgentPolicyTemplate:
        template.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(template)
        self._templates[template.template_id] = stored
        return deepcopy(stored)

    def get(self, template_id: str):
        template = self._templates.get(template_id)
        return deepcopy(template) if template is not None else None

    def list(self, status: str = None):
        matching = [
            template for template in self._templates.values() if status is None or template.status == status
        ]
        return [deepcopy(template) for template in sorted(matching, key=lambda item: item.created_at)]


class InMemoryLLMAgentPolicyTemplateInstantiationStore(LLMAgentPolicyTemplateInstantiationStore):
    """Stores durable LLM agent policy template instantiation records in
    memory, for development and testing."""

    def __init__(self):
        self._instantiations: dict[str, LLMAgentPolicyTemplateInstantiation] = {}

    def save(self, instantiation: LLMAgentPolicyTemplateInstantiation) -> LLMAgentPolicyTemplateInstantiation:
        stored = deepcopy(instantiation)
        self._instantiations[instantiation.policy_id] = stored
        return deepcopy(stored)

    def get_for_policy(self, policy_id: str):
        instantiation = self._instantiations.get(policy_id)
        return deepcopy(instantiation) if instantiation is not None else None

    def list_for_template(self, template_id: str):
        matching = [
            instantiation
            for instantiation in self._instantiations.values()
            if instantiation.template_id == template_id
        ]
        return [deepcopy(item) for item in sorted(matching, key=lambda item: item.created_at)]
