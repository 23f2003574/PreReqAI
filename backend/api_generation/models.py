from dataclasses import dataclass


@dataclass(frozen=True)
class LLMAPIGenerationResult:
    """What a generator returned for one VALIDATED documentation draft:
    files maps a relative path to its text content. The draft itself is the
    only specification -- nothing here restates or extends its fields."""

    draft_id: str
    endpoint: str
    files: dict
