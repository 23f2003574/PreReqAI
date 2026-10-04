import shutil
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
)

from backend.api.workflow_result import (
    failure_response,
    success_body,
)

from backend.platform import (
    platform,
)

from backend.session import (
    session_manager,
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

        result = pipeline.run(
            temp_path,
        )

    except Exception as exc:

        return failure_response(
            400,
            "analysis",
            f"Failed to process the uploaded paper: {exc}",
            error=exc,
            hint="Upload a text-based PDF research paper.",
        )

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )

    session = session_manager.create(
        paper_title=result.report["paper"]["title"],
        report=result.report,
        paper=result.paper,
    )

    return success_body(

        "Prerequisite Explorer",

        "session_created",

        session_id=session.session_id,

        report=result.report,
    )
