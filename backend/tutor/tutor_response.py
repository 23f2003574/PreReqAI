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

    # Who wrote the answer: "built-in" (the rule-based tutor) or "gemini:<model>"; `notes` say why the built-in tutor answered when a provider was
    # configured but could not (missing key, rate limit, timeout...). Sessions saved before these fields existed read the defaults.
    provider: str = "built-in"

    notes: list[str] = field(
        default_factory=list,
    )
