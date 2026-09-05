from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicyTemplate, LLMAgentPolicyTemplateInstantiation


class LLMAgentPolicyTemplateStore(ABC):
    """Persistence operations for durable, reusable LLM agent policy
    templates.

    Templates are not scoped to any one project/notebook/API -- the same
    save/get shape backend.agent_policy_engine.LLMAgentPolicyStore already
    uses, but list() returns every template (optionally filtered by
    status) rather than list_for_scope(), since a template is meant to be
    reused across every scope, never owned by one. There is deliberately
    no delete(): a template is retired via
    LLMAgentPolicyTemplateService.archive(), which goes through save() to
    flip its status, never a hard delete.
    """

    @abstractmethod
    def save(self, template: LLMAgentPolicyTemplate) -> LLMAgentPolicyTemplate:
        ...

    @abstractmethod
    def get(self, template_id: str) -> Optional[LLMAgentPolicyTemplate]:
        ...

    @abstractmethod
    def list(self, status: str = None) -> list:
        ...


class LLMAgentPolicyTemplateInstantiationStore(ABC):
    """Persistence for the append-only record of each instantiate() call
    -- the only place a Commit #1 policy's template/version provenance is
    preserved. There is no update() or delete(): an instantiation record
    is never overwritten or removed once recorded.
    """

    @abstractmethod
    def save(self, instantiation: LLMAgentPolicyTemplateInstantiation) -> LLMAgentPolicyTemplateInstantiation:
        ...

    @abstractmethod
    def get_for_policy(self, policy_id: str) -> Optional[LLMAgentPolicyTemplateInstantiation]:
        ...

    @abstractmethod
    def list_for_template(self, template_id: str) -> list:
        ...
