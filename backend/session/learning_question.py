from dataclasses import dataclass
from datetime import datetime


@dataclass
class LearningQuestion:

    question_id: str

    question: str

    topic: str | None

    timestamp: datetime

    answered: bool = False
