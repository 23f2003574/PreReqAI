from dataclasses import dataclass
from typing import Any, Optional

# Rule vocabulary. REQUIRED/TYPE deliberately use the same rule strings as
# backend.input_validation's LLMInputValidation so a caller reading either
# module's errors sees one vocabulary. They are re-declared here rather than
# imported because backend.input_validation depends on backend.llm -- importing
# it from inside backend.llm would invert that dependency.
REQUIRED = "required"
TYPE = "type"
UNKNOWN_FIELD = "unknown_field"
ENUM = "enum"
MINIMUM = "minimum"
MAXIMUM = "maximum"


@dataclass(frozen=True)
class LLMToolValidationError:
    """One structured reason a tool call's arguments don't match its schema.

    Mirrors backend.input_validation.LLMInputValidation's shape
    (subject / field / rule / value / message) so validation failures look
    the same wherever they come from. field is None for an error about the
    argument payload as a whole rather than one property. value carries
    whatever the rule checked against -- None for "required"/"unknown_field",
    the expected JSON Schema type name for "type", the allowed values for
    "enum", the bound for "minimum"/"maximum".
    """

    tool_name: str
    field: Optional[str]
    rule: str
    value: Any
    message: str
