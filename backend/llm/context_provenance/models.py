from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# The kinds of artifact a stored context can be traced back to. Closed, like
# Commit #1's VALID_CONTEXT_TYPES: "project_context" and "context_version"
# point at Commit #1/#2's own records and are verified against them when
# possible; "research_artifact" points at backend.session's ResearchArtifact;
# "agent_memory" points at backend.agent_execution_memory's LLMAgentMemory
# (added by backend.agent_task_context_resolution, which is the first
# consumer to attach provenance for an injected memory rather than a
# stored context -- additive only, verified against nothing in this
# module, the same trust level "external" already gets); "external"
# covers anything the repository has no store to verify against (a
# notebook cell, an uploaded file, a URL) and is accepted on trust.
VALID_SOURCE_TYPES = frozenset(
    {
        "project_context",
        "context_version",
        "research_artifact",
        "agent_memory",
        "external",
    }
)


@dataclass(frozen=True)
class LLMContextProvenance:
    """An immutable record of which project artifact a stored context came from.

    Append-only: LLMContextProvenanceService.attach() adds new records,
    nothing ever edits or removes one. A context may accumulate more than
    one record over time (e.g. it was assembled from several sources) --
    sources() returns the whole trail, get() the most recent entry.
    """

    context_id: str
    source_type: str
    source_id: str
    excerpt: str
    source_version: Optional[int] = None
    provenance_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
