from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Explicit, closed lifecycle for a strategy -- the same plain-string
# status vocabulary backend.agent_memory_promotion's
# CANDIDATE/TRUSTED/DEPRECATED and backend.llm.tool_execution's
# SUCCEEDED/FAILED already use, rather than a new Enum type. Archiving a
# strategy only ever moves it from ACTIVE to ARCHIVED (never deleted --
# see LLMAgentStrategyService.archive()); there is no automatic path back.
ACTIVE = "active"
ARCHIVED = "archived"
STATUSES = frozenset({ACTIVE, ARCHIVED})


@dataclass
class LLMAgentStrategy:
    """One proven, reusable approach for a scope, kept distinct from the
    individual execution memories that justified it.

    Unlike backend.agent_execution_memory.LLMAgentMemory -- one durable
    outcome distilled from a single completed execution -- an
    LLMAgentStrategy is a scope-level, named approach a caller
    deliberately curates from one or more such memories. source_memory_ids
    is that provenance: the LLMAgentMemory records (each already carrying
    its own execution_id and verified outcome, per Commit #1) that justify
    this strategy existing. LLMAgentStrategyService.create() verifies
    every id in it names a real memory in this same scope before a
    strategy is ever saved, so a strategy's provenance always resolves.

    Nothing here generates a strategy automatically -- creation is always
    an explicit call naming particular source memories.
    """

    scope_id: str
    name: str
    description: str
    strategy_data: Any
    source_memory_ids: list = field(default_factory=list)
    status: str = ACTIVE
    strategy_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentStrategy":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
