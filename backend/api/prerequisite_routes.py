import shutil
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
)

from starlette.concurrency import run_in_threadpool

from fastapi.responses import (
    JSONResponse,
)

from backend.api.workflow_result import (
    HTTP_STATUS,
    SUCCESS,
)

from backend.platform import (
    platform,
)

router = APIRouter(
    prefix="/api/prerequisites",
    tags=["Prerequisite Explorer"],
)

pipeline = platform.analysis


def _analyze_upload(paper: UploadFile) -> dict:
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

            shutil.copyfileobj(
                paper.file,
                temp_file,
            )

        return platform.analyze(
            temp_path,
        )

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )


@router.post("/analyze")
async def analyze_prerequisites(

    paper: UploadFile = File(...),
):

    # The analysis is blocking and CPU-bound: run on a worker thread so one
    # upload never stalls every other request the server is handling.
    outcome = await run_in_threadpool(
        _analyze_upload,
        paper,
    )

    if outcome["status"] != SUCCESS:

        return JSONResponse(
            status_code=HTTP_STATUS[outcome["status"]],
            content=outcome,
        )

    return outcome
