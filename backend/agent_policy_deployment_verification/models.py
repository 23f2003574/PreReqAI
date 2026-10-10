from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class VerificationResult:
    """verify()'s complete, deterministic outcome for one deployment_id.

    verified is True only when every check passed -- "never mark a
    deployment successful when verification fails" holds by
    construction, since this is nothing more than `not reasons`.
    reasons lists every mismatch found (never just the first one, the
    same "collect everything in one pass" shape Commit #3/#4's own
    ValidationResult/CompatibilityResult already establish for this
    series), and provenance carries both the *intended* facts (read from
    Commit #8's own deployment record) and the *actual* facts (read
    fresh from Commit #1/#6's own real, current state) side by side, so
    a mismatch is always traceable to exactly which fact disagreed.

    Deliberately carries no timestamp: verify() is a pure function of
    already-durable state, so two calls against unchanged state produce
    two equal VerificationResults, not merely two results that agree on
    everything but a wall-clock field -- the same choice Commit #4's own
    CompatibilityResult already made for the same reason.
    """

    deployment_id: str
    policy_id: str = None
    verified: bool = False
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
