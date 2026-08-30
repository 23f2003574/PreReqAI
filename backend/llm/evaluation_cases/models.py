import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Same secret-redaction convention already used by backend.llm.tool_results,
# backend.llm.tool_execution, backend.transformation_audit, and
# backend.api_recommendation_export. Kept local, as those modules keep their
# own copies, rather than refactoring them here.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _contains_secret(value: Any) -> bool:
    """Recursively checks a case's input for anything that looks like a credential."""
    if isinstance(value, str):
        return _looks_secret(value)
    if isinstance(value, dict):
        return any(
            _contains_secret(key) or _contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item) for item in value)
    return False


class InvalidEvaluationCaseError(ValueError):
    """Raised when an LLMEvaluationCase fails validation."""


class SecretInInputError(InvalidEvaluationCaseError):
    """Raised when a case's input looks like it carries a credential."""


@dataclass
class LLMEvaluationCase:
    """One registered case for measuring LLM behavior on a real task type.

    task_type names the actual project capability under evaluation (e.g.
    "notebook_analysis", "api_candidate_detection", "code_transformation" --
    whatever backend.<capability> the case is exercising), not a made-up
    category. input and expected_properties are both structured (dict)
    rather than free text: input is what the capability's service would be
    given, and expected_properties are the properties an evaluator will
    later check the resulting output against -- this commit only registers
    cases, it does not score anything.
    """

    case_id: str
    name: str
    task_type: str
    input: dict
    expected_properties: dict
    enabled: bool = True
    metadata: dict = field(default_factory=dict)

    def validate(self):
        if not self.case_id or not isinstance(self.case_id, str):
            raise InvalidEvaluationCaseError("case_id is required")

        if not self.name or not isinstance(self.name, str):
            raise InvalidEvaluationCaseError("name is required")

        if not self.task_type or not isinstance(self.task_type, str):
            raise InvalidEvaluationCaseError("task_type is required")

        if not isinstance(self.input, dict):
            raise InvalidEvaluationCaseError("input must be a structured dict")

        if not isinstance(self.expected_properties, dict):
            raise InvalidEvaluationCaseError(
                "expected_properties must be a structured dict"
            )
        if not self.expected_properties:
            raise InvalidEvaluationCaseError(
                "expected_properties must not be empty -- a case with nothing "
                "to check is not evaluable"
            )

        if not isinstance(self.enabled, bool):
            raise InvalidEvaluationCaseError("enabled must be a bool")

        if not isinstance(self.metadata, dict):
            raise InvalidEvaluationCaseError("metadata must be a dict")

        if _contains_secret(self.input) or _contains_secret(self.metadata):
            raise SecretInInputError(
                f"case {self.case_id!r} input or metadata contains something "
                "that looks like a credential"
            )
