from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CompatibilityResult:
    """check()'s complete, deterministic verdict for one
    (template, target_context) pair.

    template_id/template_version are always the exact
    LLMAgentPolicyTemplate's own identifiers -- Commit #1/#2's own
    provenance, carried through unchanged, so a caller can always trace
    a result back to precisely which template, and which version of it,
    was actually checked, the same "preserve template/version
    information" discipline Commit #1's own
    LLMAgentPolicyTemplateInstantiation already keeps for instantiate().

    reasons is empty when compatible is True, and otherwise lists every
    incompatibility found (never just the first one), each already a
    complete, human-readable, actionable sentence -- mirroring Commit
    #3's own ValidationResult "collect everything in one pass" shape,
    since this class composes Commit #3's validator as one of its own
    inputs (see LLMAgentPolicyTemplateCompatibility).

    provenance is a plain, JSON-safe dict recording exactly what was
    compared (the schema version checked, the capabilities/features the
    template references vs. what target_context declared as supported,
    the scope_id checked) -- so an incompatible verdict is never a bare
    True/False, always traceable to specific facts.
    """

    template_id: str
    template_version: int
    compatible: bool
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
