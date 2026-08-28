from dataclasses import dataclass

from ..project_context import LLMProjectContext


@dataclass
class LLMContextMatch:
    """One ranked result: a stored context plus how well it matched a query."""

    context: LLMProjectContext
    score: float
    reason: str
