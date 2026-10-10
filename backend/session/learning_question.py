from dataclasses import dataclass
from datetime import datetime

from .learning_intent import LearningIntent
from .workflow_type import WorkflowType
from .tutor_mode import TutorMode


@dataclass
class LearningQuestion:

    question_id: str

    question: str

    topic: str | None

    timestamp: datetime

    answered: bool = False

    mode: TutorMode = TutorMode.INTUITION

    intent: LearningIntent = (
        LearningIntent.UNKNOWN
    )

    workflow: WorkflowType = (
        WorkflowType.DEFAULT
    )
