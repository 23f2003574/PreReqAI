from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AgentTaskReadinessCheck:
    """One individual check LLMAgentTaskReadinessService.check() ran (or
    skipped as not applicable) against one task, in the exact order it
    ran.

    name is a stable, machine-checkable identifier (e.g.
    "lifecycle_state", "policy") -- never only a free-form message --
    the same "a stable code, not just prose" discipline
    backend.agent_risk_profile_validation.ValidationIssue.code already
    establishes for a comparable per-item report elsewhere in this
    repository. detail is the human-readable explanation, present
    whenever passed is False and optional otherwise.
    """

    name: str
    passed: bool
    detail: Optional[str] = None


@dataclass(frozen=True)
class AgentTaskReadinessResult:
    """LLMAgentTaskReadinessService.check()'s complete, deterministic
    verdict for one task_id.

    ready is exactly `not blocking_reasons` -- warnings never affect it,
    the same failed-checks/warnings split
    backend.agent_capability_execution_validation.ExecutionValidationResult
    and backend.agent_task_state_validation.AgentTaskStateValidationResult
    already keep for a comparable structured result elsewhere in this
    series. blocking_reasons collects every reason found, never only the
    first (Rule: "report every blocking reason instead of stopping at
    the first failure"). checks is every AgentTaskReadinessCheck this
    call actually ran, in order -- a task-does-not-exist result short-
    circuits with a single check entry, since nothing else about the
    task can be inspected at all.

    Computing this result never mutates, schedules, executes, or repairs
    task_id or anything it references.
    """

    ready: bool
    task_id: str
    blocking_reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    checks: list = field(default_factory=list)
