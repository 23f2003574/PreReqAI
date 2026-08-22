from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMRequestBudget:
    """Mutable, current token/cost budget state for one scope (e.g. a workspace)."""

    budget_id: str
    scope_id: str
    max_tokens: Optional[int] = None
    max_cost: Optional[float] = None
    used_tokens: int = 0
    used_cost: float = 0.0
    enabled: bool = True
