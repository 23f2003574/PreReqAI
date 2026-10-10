from abc import ABC, abstractmethod
from typing import Optional

from .models import ApprovalRequirement


class ApprovalRequirementStore(ABC):
    """Persistence operations for durable ApprovalRequirement records.

    Mirrors backend.agent_policy_engine.LLMAgentPolicyStore's own
    save/get shape -- "the repository's existing configuration/
    persistence pattern" (see Rules: "Approval state must be persisted
    using existing infrastructure") -- rather than a new persistence
    framework, plus one addition this domain genuinely needs:
    current_for_context()/set_current_for_context(), so
    LLMAgentRiskApprovalGate.evaluate() can find the one live
    requirement already scoped to a given action/context (see Rules:
    "Approval must be scoped to the specific action/context") instead
    of minting a new one on every call.

    Only an InMemory implementation is provided in this commit. A
    durable requirement embeds a full Commit #4 RiskDecision (itself
    embedding a full Commit #2/#3 RiskClassification/RiskThresholds and
    an action_context) -- none of those were designed for JSON
    round-tripping, and this series' own existing precedent for "a
    durable record that embeds another commit's full object" is
    backend.agent_policy_audit's own choice to store only compact,
    reference-based fields instead of the full object precisely to
    avoid this. Reshaping ApprovalRequirement into a compact,
    JSON-serializable audit-style record is a genuinely separate
    concern from this commit's own goal (explicit approval gating) and
    is left to a later commit rather than invented here as an
    unrelated refactor.
    """

    @abstractmethod
    def save(self, requirement: ApprovalRequirement) -> ApprovalRequirement:
        ...

    @abstractmethod
    def get(self, request_id: str) -> Optional[ApprovalRequirement]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...

    @abstractmethod
    def current_for_context(self, context_key: str) -> Optional[str]:
        """The request_id of the current requirement for context_key, or
        None if no requirement has ever been created for it."""
        ...

    @abstractmethod
    def set_current_for_context(self, context_key: str, request_id: str) -> None:
        ...
