from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTaskRecoveryGuardResult:
    """LLMAgentTaskRecoveryGuardService.validate()'s complete, read-only
    verdict on whether one already-computed recovery plan is still safe
    to execute right now -- never itself a plan or an execution result
    (Rule: "Read-only; never execute recovery"; "Do not duplicate Commit
    #4 recovery execution").

    allowed is exactly `not violations` -- warnings never affect it, the
    same failed-checks/warnings split
    backend.agent_task_readiness.AgentTaskReadinessResult and
    backend.agent_capability_execution_validation.ExecutionValidationResult
    already keep for a comparable structured result elsewhere in this
    repository. violations collects every blocking reason found, never
    only the first (the same "report every blocking reason instead of
    stopping at the first failure" convention those same result types
    already establish).

    checked_conditions names every condition this call actually evaluated
    (Rule: "Unsupported checks must not be fabricated") -- a condition
    whose own collaborator was not supplied to this service is simply
    absent from this tuple, never silently assumed to have passed.

    recommended_action echoes recovery_plan.recommended_action verbatim,
    so a caller inspecting only this result still knows what was being
    validated.
    """

    task_id: str
    recommended_action: str
    allowed: bool
    violations: tuple
    warnings: tuple
    checked_conditions: tuple
