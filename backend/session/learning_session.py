import time
from dataclasses import dataclass, field
from uuid import uuid4

from backend.models import Paper

from backend.interaction import (
    InteractionHistory,
)

from backend.navigation import (
    NavigationHistory,
    NavigationResult,
)

from .context_retriever import RetrievedContext
from .learning_gap import LearningGap
from .learning_recommendation import LearningRecommendation
from .workflow_memory import WorkflowMemory


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

    learning_gaps: list[LearningGap] = field(
        default_factory=list
    )

    recommendations: list[LearningRecommendation] = field(
        default_factory=list
    )

    workflow_memory: WorkflowMemory = field(
        default_factory=WorkflowMemory,
    )

    interaction_history: InteractionHistory = field(
        default_factory=InteractionHistory,
    )

    navigation_history: NavigationHistory = field(
        default_factory=NavigationHistory,
    )

    last_navigation: NavigationResult | None = None

    status: str = "active"

    created_at: float = field(default_factory=time.time)

    # Interactive quiz (backend.tutor.quiz_session): attempts recorded so far, and the served questions still awaiting their outcome.
    quiz_attempts: list = field(default_factory=list)

    quiz_pending: dict = field(default_factory=dict)

    # The format of the saved file (see SessionManager.SCHEMA_VERSION). A file written before versions existed has no such attribute, so it
    # reads this class default: 1, the legacy format.
    schema_version: int = 1
