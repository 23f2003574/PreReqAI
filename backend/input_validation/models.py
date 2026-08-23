from dataclasses import dataclass
from typing import Any


REQUIRED = "required"
TYPE = "type"
DEFAULT = "default"


@dataclass(frozen=True)
class LLMInputValidation:
    """One validation rule derived from an LLMInputSchema field.

    rule is either "required", "type", "default", or the name of a
    constraint key from the schema (e.g. "min", "max", "enum"). value holds
    whatever that rule needs to check against (None for "required", the
    expected type name for "type", the default itself for "default", the
    constraint's own value otherwise).
    """

    candidate_id: str
    field: str
    rule: str
    value: Any
    message: str
