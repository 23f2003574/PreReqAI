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

from backend.api.workflow_result import (
    HTTP_STATUS,
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


def _analyze_upload(paper: UploadFile, known: list[str]) -> dict:
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

        return platform.analyze(
            temp_path,
            **({'known': known} if known else {}),
        )

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )


@router.post("/analyze")
async def analyze_prerequisites(

    paper: UploadFile = File(...),
    known: list[str] = Form(default=[]),
):

    # The analysis is blocking and CPU-bound: run on a worker thread so one
    # upload never stalls every other request the server is handling.
    outcome = await run_in_threadpool(
        _analyze_upload,
        paper,
        known,
    )

    if outcome["status"] != SUCCESS:

        return JSONResponse(
            status_code=HTTP_STATUS[outcome["status"]],
            content=outcome,
        )

    return outcome


@router.post("/sessions/{session_id}/studied")
async def mark_concept_studied(

    session_id: str,
    concept: str,
):
    """Mark a concept from the session's study plan as studied; returns the updated readiness."""

    try:

        progress = platform.mark_concept_studied(session_id, concept)

    except ValueError as error:

        return JSONResponse(status_code=422, content={"status": "invalid_concept", "detail": str(error)})

    if progress is None:

        return JSONResponse(status_code=404, content={"status": "unknown_session", "detail": "No such session."})

    return {"status": "success", "session_id": session_id, **progress}
