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

    # Model answers only: the citations that were checked against the paper (each {passage_id, quote, sentence, page_number, section}, taken from the
    # stored passage, never from the model) and how the answer came about: "verified" (a model answer whose citations all matched), "fallback" (the
    # model's answer was rejected or could not be checked and the built-in tutor answered), or "" (the built-in tutor, as before).
    citations: list = field(
        default_factory=list,
    )

    grounding: str = ""
