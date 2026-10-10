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
