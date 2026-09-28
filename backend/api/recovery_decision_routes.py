from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.agent_task_recovery_execution_precondition_snapshots import (
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
)

from backend.cli import (
    build_recovery_decision_facade,
)

router = APIRouter(

    prefix="/api/tasks",

    tags=["Recovery Decision Lifecycle"],
)

facade = (
    build_recovery_decision_facade()
)


@router.post("/{task_id}/recovery-decision/evaluate")
def evaluate_recovery_decision(task_id: str):
    """Evaluate task_id's recovery execution decision lifecycle end to
    end (authoritative decision, lineage validation, impact/staleness
    detection, remediation/reconciliation, final verification) and
    return the consolidated AgentTaskRecoveryExecutionDecisionLifecycleResult.

    A blocked, unresolved, or otherwise non-terminal lifecycle is still a
    successful evaluation -- it returns 200 with that outcome in the
    body, distinguishing it from an internal failure (500), which is
    reserved for the evaluation itself not completing.
    """

    if not task_id or not task_id.strip():

        raise HTTPException(
            status_code=422,
            detail="task_id is required and must be a non-empty string",
        )

    try:

        result = facade.evaluate(
            task_id,
        )

    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to evaluate the recovery execution decision lifecycle",
        ) from exc

    return result.to_dict()
