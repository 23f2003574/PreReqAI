from dataclasses import asdict, dataclass, field
from typing import Optional

# Mirrors backend.llm.security_health.LLMSecurityHealthService's own
# HEALTHY/DEGRADED/.../UNKNOWN vocabulary and "worst signal wins"
# aggregation -- the closest existing health-assessment precedent in
# this repository, reused rather than inventing a second one. UNKNOWN
# is the answer whenever there is not enough evidence to say anything
# else -- "do not infer health from unavailable evidence" holds by
# having an explicit "insufficient evidence" outcome to fall back to,
# rather than defaulting a missing signal into HEALTHY or UNHEALTHY.
HEALTHY = "healthy"
DEGRADED = "degraded"
UNHEALTHY = "unhealthy"
UNKNOWN = "unknown"
STATUSES = frozenset({HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN})

# Severity precedence, worst first -- the same "if CRITICAL in
# severities: return CRITICAL" shape LLMSecurityHealthService._overall()
# already uses.
_SEVERITY_ORDER = (UNHEALTHY, DEGRADED, UNKNOWN, HEALTHY)


def overall_status(signals: set) -> str:
    """The single worst status among signals, by _SEVERITY_ORDER --
    reused by both assess() and, implicitly, assess_scope() (which
    simply reports each deployment's own already-combined status,
    never re-aggregates across deployments)."""
    for status in _SEVERITY_ORDER:
        if status in signals:
            return status
    return HEALTHY


@dataclass(frozen=True)
class HealthResult:
    """assess()'s complete, deterministic, read-only verdict for one
    Commit #8 deployment record.

    Preserves exactly the source references a caller needs to trace
    this verdict back to real, already-durable evidence:
    deployment_id/policy_id/scope_id/template_id/template_version are
    all read verbatim from Commit #8's own record (or, for
    template_id/template_version, from Commit #9's own verification
    provenance when the record's own copy could not be resolved) --
    never recomputed independently. reasons lists every contributing
    signal (never just the worst one), and provenance carries the raw
    evidence (verification result, current-deployment comparison, and
    recent-failure count) this verdict was built from.

    No timestamp: assess() is a pure function of already-durable Commit
    #7-#9 state, so two calls against unchanged state produce two equal
    HealthResults, the same choice Commit #4/#9's own CompatibilityResult/
    VerificationResult already made for the same reason.
    """

    deployment_id: str
    status: str
    policy_id: Optional[str] = None
    scope_id: Optional[str] = None
    template_id: Optional[str] = None
    template_version: Optional[int] = None
    reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
