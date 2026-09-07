from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# No multi-stage progressive rollout precedent exists anywhere in this
# repository (confirmed by inspection: the closest deployment
# infrastructure, backend.agent_policy_deployment_orchestration, is a
# single-shot deploy -> verify -> health -> governance -> rollback
# pipeline, never a paused/resumed/staged progression) -- so this is
# the "minimal deterministic staged strategy appropriate to existing
# scope semantics" the goal's own Rules explicitly sanction inventing
# when none already exists. This series' own scope model has no
# sub-scope environments or traffic percentages to stage across (Rule:
# "No runtime traffic shifting ... unless the repository already
# provides those capabilities" -- it does not), so STANDARD stages
# progressive *safety checkpoints* around the one real mutation a
# rollout ever performs (Commit #6's own activate()) rather than a
# population rollout: re-verify nothing has changed since approval,
# activate through the real mechanism, then confirm the activation
# actually took effect.
STANDARD = "standard"
STANDARD_STAGES = ("pre_flight", "activate", "verify")
STRATEGIES = frozenset({STANDARD})

IN_PROGRESS = "in_progress"
PAUSED = "paused"
COMPLETED = "completed"
FAILED = "failed"
STATES = frozenset({IN_PROGRESS, PAUSED, COMPLETED, FAILED})


class InvalidRiskProfileRolloutError(ValueError):
    """Raised when a RiskProfileRollout's fields are missing, invalid,
    or inconsistent with its own state."""


@dataclass(frozen=True)
class RiskProfileRollout:
    """Immutable snapshot of one controlled rollout of an approved
    Commit #1 risk profile version across its scope.

    A value object only, performing no stage transition of its own;
    LLMAgentRiskProfileRolloutService produces a new record (via
    dataclasses.replace) for every transition rather than mutating an
    existing one -- the same "terminal once decided,
    dataclasses.replace()-not-mutate" discipline
    backend.agent_policy_risk_approval.ApprovalRequirement and this
    series' own Commit #10 RiskProfileApproval already established.

    current_stage is the name of the most recently *succeeded* stage in
    stages, or None before advance_rollout() has ever been called --
    never the stage about to run, so "which stages have actually
    completed" is always answerable by inspection alone, and "never
    silently skip a stage" is directly checkable (current_stage is
    always either None or immediately preceded by every earlier entry
    in stages).

    state is IN_PROGRESS while stages are being worked through, PAUSED
    when progression has been deliberately halted (current_stage/stages
    are left completely untouched by pausing -- "pause must prevent
    further progression without losing rollout state"), FAILED when a
    stage's own safety check or action did not succeed (current_stage
    still names the last stage that *did* succeed, never the failed
    one -- the previously active profile is left exactly as it was,
    since only the "activate" stage ever calls Commit #6's real
    activate(), and that call either fully succeeds or changes
    nothing), and COMPLETED only once complete_rollout() has explicitly
    confirmed every stage in stages already succeeded.

    provenance carries whatever evidence the most recent stage
    attempt produced (Commit #3 validation / Commit #5 compatibility on
    "pre_flight", Commit #6's own ActivationResult on "activate", the
    live (profile, version) pair on "verify"), plus a failure_reason
    when state is FAILED -- never re-derived later from a stale lookup.
    """

    rollout_id: str
    profile_id: str
    version: int
    scope_id: str
    strategy: str
    state: str
    current_stage: Optional[str]
    stages: tuple
    provenance: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        self._require_text(self.rollout_id, "rollout ID")
        self._require_text(self.profile_id, "profile ID")
        self._require_text(self.scope_id, "scope ID")

        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise InvalidRiskProfileRolloutError("version must be a positive integer")
        if self.strategy not in STRATEGIES:
            raise InvalidRiskProfileRolloutError(f"strategy {self.strategy!r} is not one of {sorted(STRATEGIES)}")
        if self.state not in STATES:
            raise InvalidRiskProfileRolloutError(f"state {self.state!r} is not one of {sorted(STATES)}")
        if not isinstance(self.stages, tuple) or not self.stages:
            raise InvalidRiskProfileRolloutError("stages must be a non-empty tuple")
        if self.current_stage is not None and self.current_stage not in self.stages:
            raise InvalidRiskProfileRolloutError(f"current_stage {self.current_stage!r} is not one of {self.stages}")

        if self.state == COMPLETED:
            if self.current_stage != self.stages[-1]:
                raise InvalidRiskProfileRolloutError("a COMPLETED rollout must have succeeded every stage")
            if self.completed_at is None:
                raise InvalidRiskProfileRolloutError("a COMPLETED rollout must have completed_at")
        elif self.completed_at is not None:
            raise InvalidRiskProfileRolloutError("only a COMPLETED rollout can have completed_at")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidRiskProfileRolloutError(f"{field_name} is required and must be non-blank")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["stages"] = list(self.stages)
        data["started_at"] = self.started_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        return data


def new_rollout_id() -> str:
    return str(uuid4())
