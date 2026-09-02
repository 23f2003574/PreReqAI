from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMAgentMemoryQuery:
    """One request for Commit #1 memory relevant to a new agent task.

    memory_types, when given, restricts results to those memory_type
    values (an OR filter, not AND -- a memory matching any of them
    qualifies). outcome_filter, when given, restricts results to that
    single outcome. limit, when given, caps how many ranked results
    retrieve() returns; omitted (None) means "every match in scope."
    """

    scope_id: str
    query: str = ""
    memory_types: Optional[list] = field(default=None)
    outcome_filter: Optional[str] = None
    limit: Optional[int] = None
