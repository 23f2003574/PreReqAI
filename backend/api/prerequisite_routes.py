import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
)

from starlette.concurrency import run_in_threadpool

from fastapi.responses import (
    JSONResponse,
)

from backend.api.session_routes import (
    session_not_found,
)

from backend.api.workflow_result import (
    HTTP_STATUS,
    failure_response,
    SUCCESS,
    limit_exceeded_body,
)

from backend.platform import (
    platform,
)

router = APIRouter(
    prefix="/api/prerequisites",
    tags=["Prerequisite Explorer"],
)

pipeline = platform.analysis


# Far above any real paper; it only stops an upload from filling the disk. (The CLI's
# --max-file-mb is the adjustable equivalent.) Over the limit is the same
# `limit_exceeded` outcome (HTTP 413) the analysis limits already produce.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

_CHUNK_BYTES = 1024 * 1024


def _hide_server_path(outcome: dict, temp_path: str, name: str) -> dict:
    """Error text names the upload by its own file name, not the server's temporary copy."""

    for holder in (outcome, outcome.get("error")):

        if isinstance(holder, dict):

            for key in ("detail", "message", "hint"):

                if isinstance(holder.get(key), str):

                    holder[key] = holder[key].replace(temp_path, name)

    return outcome


def _analyze_upload(paper: UploadFile, known: list[str], studied: list[str], diagnostics: bool = False) -> dict:
    """Blocking work (copy the upload, run the analysis): called off the event loop."""

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    )

    temp_path = temp_file.name

    # The copy is inside the try, so a failed or interrupted upload never
    # leaves its partial temp file behind.
    try:

        with temp_file:

            copied = 0

            while chunk := paper.file.read(_CHUNK_BYTES):

                copied += len(chunk)

                if copied > MAX_UPLOAD_BYTES:

                    return limit_exceeded_body(
                        "analysis",
                        f"The paper is larger than the limit of {MAX_UPLOAD_BYTES} bytes.",
                        hint="Upload a smaller paper; nothing was kept.",
                    )

                temp_file.write(chunk)

        outcome = platform.analyze(
            temp_path,
            **({'diagnostics': True} if diagnostics else {}),
            **({'known': known} if known else {}),
            **({'studied': studied} if studied else {}),
        )

        return _hide_server_path(outcome, temp_path, Path(paper.filename or "").name or "the uploaded paper")

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )


@router.post("/analyze")
async def analyze_prerequisites(

    paper: UploadFile = File(...),
    known: list[str] = Form(default=[]),
    studied: list[str] = Form(default=[]),
    diagnostics: bool = Form(default=False),
):

    # The analysis is blocking and CPU-bound: run on a worker thread so one
    # upload never stalls every other request the server is handling.
    outcome = await run_in_threadpool(
        _analyze_upload,
        paper,
        known,
        studied,
        diagnostics,
    )

    if outcome["status"] != SUCCESS:

        return JSONResponse(
            status_code=HTTP_STATUS[outcome["status"]],
            content=outcome,
        )

    return outcome


def _update_studied(session_id: str, concept: str, studied: bool):

    action = platform.mark_concept_studied if studied else platform.unmark_concept_studied

    try:

        progress = action(session_id, concept)

    except ValueError as error:

        return failure_response(
            422,
            "study_progress",
            str(error),
            hint="Use a concept name from the session's study plan (GET /api/session/{session_id} lists study_progress).",
        )

    if progress is None:

        return session_not_found(session_id)

    return {"status": "success", "session_id": session_id, **progress}


@router.post("/sessions/{session_id}/studied")
async def mark_concept_studied(

    session_id: str,
    concept: str,
):
    """Mark a concept from the session's study plan as studied; returns the updated readiness."""

    return _update_studied(session_id, concept, True)


@router.delete("/sessions/{session_id}/studied")
async def unmark_concept_studied(

    session_id: str,
    concept: str,
):
    """Undo a mistaken mark: the concept goes back to not studied and readiness drops accordingly."""

    return _update_studied(session_id, concept, False)


@router.post("/sessions/{session_id}/known")
async def mark_concept_known(

    session_id: str,
    concept: str,
):
    """Drop a concept the learner already knows from the session's study plan; the plan, time estimate and readiness are rebuilt."""

    try:

        report = platform.mark_concept_known(session_id, concept)

    except ValueError as error:

        return failure_response(
            422,
            "study_progress",
            str(error),
            hint="Use a concept name from the session's study plan (GET /api/session/{session_id}).",
        )

    if report is None:

        return session_not_found(session_id)

    # Same fields as the /studied endpoints answer with, plus the rebuilt report (the plan itself changed).
    return {
        "status": "success",
        "session_id": session_id,
        "study_progress": report["study_progress"],
        "readiness": report["readiness"],
        "report": report,
    }
