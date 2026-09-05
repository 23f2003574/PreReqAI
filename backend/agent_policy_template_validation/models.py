from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ValidationIssue:
    """One concrete, actionable problem found by
    LLMAgentPolicyTemplateValidator.

    code names the kind of problem as a stable, machine-checkable string
    (e.g. "missing_rules", "invalid_rule", "unknown_parameter") -- never
    a free-form message alone, so a caller can branch on it without
    string-matching. message is the human-readable explanation. path
    names exactly where the problem was found (e.g.
    "rules[1].effect", "parameters.tool_name"), or None when the issue
    concerns the input as a whole (e.g. it was not a dict at all) --
    together this is what "return actionable validation errors" means in
    practice: enough to jump straight to the offending field, never just
    "something is wrong".
    """

    code: str
    message: str
    path: str = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    """The complete, deterministic outcome of one validate()/
    validate_definition()/validate_parameters() call.

    issues always lists every problem found in that single pass, never
    just the first one -- unlike Commit #1's own
    LLMAgentPolicyTemplateService, which raises and stops at the first
    validation failure, this is what lets a caller fix every problem at
    once instead of resubmitting one fix at a time. Side-effect free:
    computing a ValidationResult never mutates, persists, or registers
    anything.
    """

    issues: list = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict:
        return {"is_valid": self.is_valid, "issues": [issue.to_dict() for issue in self.issues]}
