from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CompatibilityResult:
    """check()'s complete, deterministic verdict for one
    (profile, target_context) pair.

    profile_id/profile_version are always the exact LLMAgentRiskProfile's
    own identifiers -- Commit #1/#4's own provenance, carried through
    unchanged, so a caller can always trace a result back to precisely
    which profile, and which version of it, was actually checked (Rule:
    "Preserve profile/version provenance").

    reasons is empty when compatible is True, and otherwise lists every
    incompatibility found (never just the first one), each already a
    complete, human-readable, actionable sentence -- mirroring Commit
    #3's own ValidationResult "collect everything in one pass" shape,
    since this class composes Commit #3's validator as one of its own
    inputs (see LLMAgentRiskProfileCompatibility). Same shape as
    backend.agent_policy_template_compatibility.CompatibilityResult,
    mirrored locally rather than imported -- that module checks an
    unrelated record (policy templates), and this repository's own
    established precedent is a from-scratch, same-shape reimplementation
    local to the module that needs it, not a cross-domain import.

    provenance is a plain, JSON-safe dict recording exactly what was
    compared (the schema version checked, the risk levels/action fields/
    specificity tier the profile references vs. what target_context
    declared as supported, the scope_id checked) -- so an incompatible
    verdict is never a bare True/False, always traceable to specific
    facts.
    """

    profile_id: str
    profile_version: int
    compatible: bool
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
