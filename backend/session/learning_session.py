from dataclasses import dataclass, field
from uuid import uuid4

from backend.models import Paper

from .context_retriever import RetrievedContext


@dataclass
class LearningSession:

    session_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    paper_title: str = ""

    report: dict = field(default_factory=dict)

    paper: Paper | None = None

    active_concept: str | None = None

    current_context: RetrievedContext | None = None

    conversation_history: list[dict] = field(
        default_factory=list
    )

    status: str = "active"
