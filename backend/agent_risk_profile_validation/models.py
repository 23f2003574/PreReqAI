from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ValidationIssue:
    """One concrete, actionable problem found by
    LLMAgentRiskProfileValidator.

    code names the kind of problem as a stable, machine-checkable string
    (e.g. "missing_scope_id", "unknown_risk_level",
    "malformed_action_rule") -- never a free-form message alone, so a
    caller can branch on it without string-matching. message is the
    human-readable explanation. path names exactly where the problem
    was found (e.g. "action_rules[1].level", "default_level"), or None
    when the issue concerns the input as a whole (e.g. it was not an
    LLMAgentRiskProfile at all) -- together this is what "return
    actionable errors" means in practice.

    Same shape as backend.agent_policy_template_validation.
    ValidationIssue, mirrored locally rather than imported -- that
    module validates an unrelated record (policy templates), and this
    repository's own established precedent (see
    backend.agent_policy_risk_assessment.LEVEL_LOW et al.'s own
    docstring) is a from-scratch, same-shape reimplementation local to
    the module that needs it, not a cross-domain import.
    """

    code: str
    message: str
    path: str = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    """The complete, deterministic outcome of one validate()/
    validate_action_rules() call.

    issues always lists every problem found in that single pass, never
    just the first one -- unlike Commit #1's own
    LLMAgentRiskProfileService, which raises and stops at the first
    validation failure, this lets a caller see every problem at once
    before ever attempting to persist or resolve a profile.
    Deterministic and side-effect free: computing a ValidationResult
    never mutates, persists, or resolves anything.
    """

    issues: list = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict:
        return {"is_valid": self.is_valid, "issues": [issue.to_dict() for issue in self.issues]}
