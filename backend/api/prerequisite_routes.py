import shutil
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
)

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


@router.post("/analyze")
async def analyze_prerequisites(

    paper: UploadFile = File(...),
):

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

        outcome = platform.analyze(
            temp_path,
        )

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )

    if outcome["status"] != SUCCESS:

        return JSONResponse(
            status_code=HTTP_STATUS[outcome["status"]],
            content=outcome,
        )

    return outcome
