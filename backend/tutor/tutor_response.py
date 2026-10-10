from dataclasses import dataclass, field


@dataclass
class TutorResponse:
    """
    Standard response format for every
    tutoring engine in PreReqAI.
    """

    answer: str

    confidence: float

    supporting_concepts: list[str] = field(
        default_factory=list,
    )

    supporting_sections: list[str] = field(
        default_factory=list,
    )

    suggested_followups: list[str] = field(
        default_factory=list,
    )
