import math
import os
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

from backend.ingestion.research_source_detector import (
    ResearchSourceDetector,
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


def _server_limits():
    """The AnalysisLimits PREREQAI_MAX_ANALYSIS_SECONDS asks for, so one pathological paper cannot hold an HTTP worker
    forever (the CLI has --max-seconds); None, the default, when it is unset, blank, not a positive number or not finite."""
    try:
        seconds = float(os.environ.get("PREREQAI_MAX_ANALYSIS_SECONDS", "").strip())
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    from backend.platform import AnalysisLimits

    return AnalysisLimits(max_seconds=seconds)


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
            **({'limits': limits} if (limits := _server_limits()) else {}),
            **({'diagnostics': True} if diagnostics else {}),
            **({'known': known} if known else {}),
            **({'studied': studied} if studied else {}),
        )

        return _hide_server_path(outcome, temp_path, Path(paper.filename or "").name or "the uploaded paper")

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )


def _analyze_source(source: str, known: list[str], studied: list[str], diagnostics: bool):
    """Analyse an arXiv link or DOI. Only those are accepted: a server file path in `source` must never be read."""

    try:

        detected = ResearchSourceDetector().detect(source)

    except ValueError:

        detected = None

    if detected is None or detected.source_type not in ("arxiv", "doi"):

        return failure_response(
            422,
            "analysis",
            f"`source` must be an arXiv link or a DOI, not: {source}",
            hint="Upload a PDF as `paper` instead.",
        )

    outcome = platform.analyze(
        detected.original_input,
        **({'limits': limits} if (limits := _server_limits()) else {}),
        **({'diagnostics': True} if diagnostics else {}),
        **({'known': known} if known else {}),
        **({'studied': studied} if studied else {}),
    )

    if outcome["status"] != SUCCESS:

        return JSONResponse(status_code=HTTP_STATUS[outcome["status"]], content=outcome)

    return outcome


@router.post("/analyze")
async def analyze_prerequisites(

    paper: UploadFile | None = File(default=None),
    source: str | None = Form(default=None),
    known: list[str] = Form(default=[]),
    studied: list[str] = Form(default=[]),
    diagnostics: bool = Form(default=False),
):
    """Analyse an uploaded PDF (`paper`) or, instead, an arXiv link or DOI (`source`)."""

    if (paper is None) == (source is None):

        return failure_response(
            422,
            "input",
            "Invalid request: paper: Field required (send exactly one of `paper`, a PDF upload, or `source`, an arXiv link or DOI).",
            hint="Upload the PDF as `paper`, or pass `source` such as https://arxiv.org/abs/1706.03762 or 10.1145/3292500.3330701.",
        )

    if source is not None:

        return await run_in_threadpool(_analyze_source, source, known, studied, diagnostics)

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


def _unsaved(response: dict) -> dict:
    """The change was applied in memory; when it could not be written to PREREQAI_SESSION_DIR, say so (as analysis does)
    instead of letting the learner believe their progress will survive a server restart."""
    from backend.session import session_manager

    if not session_manager.last_save_ok:
        response["warnings"] = [
            "This change could not be saved to PREREQAI_SESSION_DIR, so it will not survive a server restart; "
            "check that the directory exists and is writable."
        ]
    return response


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

    return _unsaved({"status": "success", "session_id": session_id, **progress})


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
    return _unsaved({
        "status": "success",
        "session_id": session_id,
        "study_progress": report["study_progress"],
        "readiness": report["readiness"],
        "report": report,
    })


@router.delete("/sessions/{session_id}/known")
async def unmark_concept_known(

    session_id: str,
    concept: str,
):
    """Undo a mistaken "known": the concept returns to the study plan; the plan, time estimate and readiness are rebuilt."""

    try:

        report = platform.unmark_concept_known(session_id, concept)

    except ValueError as error:

        return failure_response(
            422,
            "study_progress",
            str(error),
            hint="Use a concept you marked known in this session (POST /api/prerequisites/sessions/{session_id}/known).",
        )

    if report is None:

        return session_not_found(session_id)

    return _unsaved({
        "status": "success",
        "session_id": session_id,
        "study_progress": report["study_progress"],
        "readiness": report["readiness"],
        "report": report,
    })
