from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMSecurityPolicySimulation:
    """A dry-run preview of what Commit #5's enforcement would do to a
    request/response, produced only by
    LLMSecurityPolicySimulationService.simulate_input()/simulate_output()
    and never by LLMSecurityPolicyService itself -- a distinct type, so a
    caller can never mistake a preview for a real enforcement outcome
    (see Rules: "Clearly distinguish simulated vs enforced decisions").

    decision/policies/findings are exactly what
    LLMSecurityPolicyService.check_input()/check_output() already
    computed (see LLMPolicyDecision) -- a simulation can never diverge
    from what real enforcement would decide for the same input, because
    it is the same read-only check, not a second policy engine.
    findings holds the actual Commit #1/#2 finding objects -- safe to
    expose because their own evidence is already guaranteed redacted by
    Commit #1/#2's rules. redactions previews what would be redacted
    using Commit #3's own detect(): {"location", "pattern"} pairs, never
    the matched text itself, so a secret is never exposed even in a dry
    run (see Rules: "Never expose detected secrets"). would_block is
    decision == BLOCK, named distinctly from LLMPolicyDecision's own
    "blocking" to keep this preview from reading like a real decision.
    """

    decision: str
    policies: tuple = field(default_factory=tuple)
    findings: tuple = field(default_factory=tuple)
    redactions: tuple = field(default_factory=tuple)
    would_block: bool = False
