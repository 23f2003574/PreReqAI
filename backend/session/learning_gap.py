from dataclasses import dataclass


@dataclass
class LearningGap:

    concept: str

    incorrect_attempts: int

    mastery: float
