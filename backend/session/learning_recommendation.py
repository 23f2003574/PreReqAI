from dataclasses import dataclass

from .tutor_mode import TutorMode


@dataclass
class LearningRecommendation:

    concept: str

    priority: str

    recommendation: str

    suggested_mode: TutorMode
