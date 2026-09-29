from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import (
    JSONResponse,
)

from backend.agent_task_recovery_execution_precondition_snapshots import (
    HEALTH_UNAVAILABLE,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError,
)

from backend.cli import (
    build_recovery_decision_facade,
    build_recovery_decision_health_service,
    build_recovery_decision_readiness_service,
)

router = APIRouter(

    prefix="/api/tasks",

    tags=["Recovery Decision Lifecycle"],
)

facade = (
    build_recovery_decision_facade()
)

health_service = (
    build_recovery_decision_health_service()
)

readiness_service = (
    build_recovery_decision_readiness_service()
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


@router.get("/{task_id}/recovery-decision/diagnostics")
def diagnose_recovery_decision(task_id: str):
    """Diagnostic-only: report task_id's recovery execution decision
    lifecycle health (#6) and per-dependency diagnostics (#7), without
    evaluating or changing anything -- never calls facade.evaluate().

    healthy/degraded/blocked all return 200 with the full result body,
    distinguished only by its own status field -- a blocked or degraded
    task is still a successful diagnosis. An UNAVAILABLE verdict (an
    infrastructure/dependency problem, not a task-level one) is instead
    mapped through this API's existing infrastructure-failure convention
    (503), while still returning the same full, structured body so the
    dependency that is actually down stays visible -- never collapsed
    into a bare error string the way a raised exception is.
    """

    if not task_id or not task_id.strip():

        raise HTTPException(
            status_code=422,
            detail="task_id is required and must be a non-empty string",
        )

    try:

        result = health_service.check(
            task_id,
        )

    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to diagnose the recovery execution decision lifecycle",
        ) from exc

    if result.status == HEALTH_UNAVAILABLE:

        return JSONResponse(
            status_code=503,
            content=result.to_dict(),
        )

    return result.to_dict()


@router.get("/recovery-decision/readiness")
def recovery_decision_readiness(task_id: str = None):
    """Deploy/CI readiness gate (#13): composes configuration validation
    (#12), dependency diagnostics (#7), and -- when task_id is given --
    that task's lifecycle health (#6) into one ready/blocked verdict.
    Diagnostic-only: never calls facade.evaluate() or any mutating
    service.

    Both READY and BLOCKED return 200 with the full result body, the
    same "a domain outcome is not an HTTP error" convention this
    router's other endpoints already use -- a CI/deployment check reads
    the body's own status field, exactly like a Kubernetes readiness
    probe reads its response payload rather than relying on status code
    alone for a "blocked" verdict.
    """

    if task_id is not None and not task_id.strip():

        raise HTTPException(
            status_code=422,
            detail="task_id must be a non-empty string when given",
        )

    try:

        result = readiness_service.check(
            task_id,
        )

    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to compute recovery execution decision lifecycle readiness",
        ) from exc

    return result.to_dict()
