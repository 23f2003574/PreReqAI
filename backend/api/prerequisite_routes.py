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
    FAILURE,
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

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    ) as temp_file:

        shutil.copyfileobj(
            paper.file,
            temp_file,
        )

        temp_path = temp_file.name

    try:

        outcome = platform.analyze(
            temp_path,
        )

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )

    if outcome["status"] == FAILURE:

        return JSONResponse(
            status_code=400,
            content=outcome,
        )

    return outcome
