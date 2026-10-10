from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from backend.llm.tools import InvalidToolDefinitionError, validate_input_schema
from backend.llm.tool_validation import ENUM, MAXIMUM, MINIMUM, REQUIRED, TYPE, UNKNOWN_FIELD

# check vocabulary: which part of a contract a violation concerns.
CHECK_INPUT = "input"
CHECK_OUTPUT = "output"
CHECK_REQUIREMENTS = "requirements"
CHECKS = frozenset({CHECK_INPUT, CHECK_OUTPUT, CHECK_REQUIREMENTS})

# rule vocabulary for check_requirements()'s own two failure kinds --
# REQUIRED/TYPE/UNKNOWN_FIELD/ENUM/MINIMUM/MAXIMUM above (reused directly
# from backend.llm.tool_validation, not redeclared) already cover every
# schema/payload failure validate_input()/validate_output() can produce;
# MISSING_CONTEXT and REQUIREMENT_NOT_MET are the two new kinds this
# module actually introduces, since neither of tool_validation's own
# checks has anything to say about a context dict.
MISSING_CONTEXT = "missing_context"
REQUIREMENT_NOT_MET = "requirement_not_met"


class InvalidCapabilityContractError(ValueError):
    """Raised when an LLMAgentCapabilityContract's fields are missing,
    blank, or malformed -- including a structurally invalid input_schema
    or output_schema (propagated from
    backend.llm.tools.validate_input_schema, the same structural JSON
    Schema check backend.llm.tools.LLMToolRegistryService and
    backend.llm.tool_validation.LLMToolValidationService already share,
    reused here rather than a second copy of those rules)."""


@dataclass(frozen=True)
class LLMAgentCapabilityContractViolation:
    """One structured reason a payload or context failed one check
    (input/output schema, or requirements) against one
    LLMAgentCapabilityContract.

    Mirrors backend.llm.tool_validation.LLMToolValidationError's shape
    (field / rule / value / message) exactly, so a contract violation
    reads the same as a tool-argument validation failure -- extended
    with capability_id/version/check so a violation is traceable to
    the exact contract that produced it. field is None for a violation
    about the payload/context as a whole rather than one property.
    """

    capability_id: str
    version: str
    check: str
    field: Optional[str]
    rule: str
    value: Any
    message: str


@dataclass(frozen=True)
class LLMAgentCapabilityContractCheck:
    """The complete, structured outcome of one validate_input()/
    validate_output()/check_requirements() call -- never just a bare
    True/False or a raised exception for an ordinary payload/context
    mismatch, so every reason a check failed is always reported at once
    (Rule: "missing required context or requirements must produce
    structured failures"), the same "report every problem, not just the
    first" discipline
    backend.llm.tool_validation.ToolArgumentValidationError already
    keeps for tool arguments.

    valid is a convenience: exactly `not violations`.
    """

    capability_id: str
    version: str
    check: str
    valid: bool
    violations: list


@dataclass(frozen=True)
class LLMAgentCapabilityContract:
    """One immutable, versioned description of what a Commit #1
    LLMAgentCapability accepts, produces, and requires -- never itself an
    executable thing (Rule: "no capability execution belongs here").

    input_schema/output_schema are plain JSON Schema objects, structurally
    checked via backend.llm.tools.validate_input_schema -- the exact same
    {"type": "object", "properties": {...}, "required": [...]} shape
    backend.llm.tools.LLMToolDefinition.input_schema already uses, reused
    here rather than a parallel schema language.

    required_context is a list of context keys that must merely be
    *present* for this contract to be satisfiable (existence only, any
    value, even a falsy one). requirements is a {field: expected}
    constraint dict checked against a caller-supplied context the same
    {field: expected} shape (expected may be a single value or a
    list/tuple/set of acceptable values) that
    backend.agent_policy_engine.LLMAgentPolicyRule.match and
    backend.agent_risk_profile.RiskProfileActionRule.match already use --
    reused here for a distinct purpose (a value-level precondition rather
    than a rule match) but the exact same shape, never a second matching
    language.

    A contract is immutable once registered: Commit #3's own
    LLMAgentCapabilityContractService has no update() -- a new version
    of a capability that needs a new contract registers a new
    LLMAgentCapabilityContract for that new version instead, leaving
    every already-registered version's contract exactly as it was (Rule:
    "contract changes must not silently invalidate existing versions").
    """

    capability_id: str
    version: str
    input_schema: dict
    output_schema: dict
    required_context: list = field(default_factory=list)
    requirements: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    contract_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.capability_id or not isinstance(self.capability_id, str):
            raise InvalidCapabilityContractError("capability_id is required and must be a non-empty string")
        if not self.version or not isinstance(self.version, str):
            raise InvalidCapabilityContractError("version is required and must be a non-empty string")

        self._validate_schema(self.input_schema, "input_schema")
        self._validate_schema(self.output_schema, "output_schema")

        if not isinstance(self.required_context, list) or not all(
            isinstance(item, str) and item.strip() for item in self.required_context
        ):
            raise InvalidCapabilityContractError("required_context must be a list of non-empty strings")

        if not isinstance(self.requirements, dict) or not all(
            isinstance(key, str) and key.strip() for key in self.requirements
        ):
            raise InvalidCapabilityContractError("requirements must be a dict with non-empty string keys")

        if not isinstance(self.metadata, dict):
            raise InvalidCapabilityContractError("metadata must be a dict")

    @staticmethod
    def _validate_schema(schema, field_name: str):
        try:
            validate_input_schema(schema)
        except InvalidToolDefinitionError as error:
            raise InvalidCapabilityContractError(f"{field_name} is invalid: {error}") from error

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentCapabilityContract":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
