from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.llm.context_provenance import LLMContextProvenance


def provenance_to_dict(source: Optional[LLMContextProvenance]) -> Optional[dict]:
    if source is None:
        return None

    data = asdict(source)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    return data


def provenance_from_dict(data: Optional[dict]) -> Optional[LLMContextProvenance]:
    if data is None:
        return None
    payload = dict(data)
    created_at = payload.get("created_at")
    if isinstance(created_at, str):
        payload["created_at"] = datetime.fromisoformat(created_at)
    return LLMContextProvenance(**payload)


@dataclass(frozen=True)
class ContextProvenanceEntry:
    """One source's own contribution within a ContextProvenanceRecord.

    source is Commit #1-of-the-original-context-injection-series' own
    backend.llm.context_provenance.LLMContextProvenance -- the
    repository's existing provenance type, embedded verbatim, never
    reshaped -- or None when the package carried no provenance record
    for source_id at all (itself a meaningful, reportable fact, not an
    error swallowed here). source_version is that same record's own
    source_version, pulled out for direct access.
    """

    source_id: str
    source: Optional[LLMContextProvenance]
    source_version: Optional[int]
    selection_reason: Optional[str]
    transformation: Optional[str]
    included: bool

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source": provenance_to_dict(self.source),
            "source_version": self.source_version,
            "selection_reason": self.selection_reason,
            "transformation": self.transformation,
            "included": self.included,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextProvenanceEntry":
        payload = dict(data)
        payload["source"] = provenance_from_dict(payload.get("source"))
        return cls(**payload)


@dataclass(frozen=True)
class ContextProvenanceRecord:
    """One immutable snapshot of a task's full context lineage, written by
    LLMAgentTaskContextProvenanceService.record() for one AgentContextPackage.

    Frozen, and entries is a tuple (not a list) -- structurally immutable,
    the same discipline backend.agent_task_context.
    LLMAgentTaskContextSnapshot already established for this series' own
    point-in-time records (Rule: "immutable provenance records once
    written"). Multiple records accumulate per task_id over time (one per
    record() call, e.g. once per packaging attempt) -- get(task_id)
    returns the whole append-only trail, the same shape backend.llm.
    context_provenance.LLMContextProvenanceService.sources() already
    keeps for its own, single-context-scoped trail.

    Never carries raw context/memory content -- only ids, the existing
    LLMContextProvenance metadata (itself already secret-screened at
    creation, per backend.llm.context_provenance.LLMContextProvenanceService.
    validate()), and human-readable reason/transformation text pulled
    from Commit #2/#3's own already-computed resolution_reasons/reasons
    dicts (Rule: "never persist raw secrets or sensitive payloads").
    """

    record_id: str
    task_id: str
    entries: tuple
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "entries": [entry.to_dict() for entry in self.entries],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextProvenanceRecord":
        payload = dict(data)
        payload["entries"] = tuple(ContextProvenanceEntry.from_dict(entry) for entry in payload.get("entries", []))
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            payload["created_at"] = datetime.fromisoformat(created_at)
        return cls(**payload)


@dataclass(frozen=True)
class ContextProvenanceTrace:
    """trace()'s answer for one specific source_id: its current, complete
    lineage, using only existing repository types (LLMContextProvenance
    for source; plain str/bool/datetime for everything else -- no new
    lineage/audit type invented beyond this bundling).
    """

    source: Optional[LLMContextProvenance]
    source_version: Optional[int]
    selection_reason: Optional[str]
    transformation: Optional[str]
    included: bool
    timestamp: datetime


def default_record_id() -> str:
    return str(uuid4())
