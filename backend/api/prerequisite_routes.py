import shutil
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
)

from backend.pipeline import (
    ResearchPaperPipeline,
)

from backend.session import (
    session_manager,
)

router = APIRouter(
    prefix="/api/prerequisites",
    tags=["Prerequisite Explorer"],
)

pipeline = ResearchPaperPipeline()


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

        raise HTTPException(
            status_code=400,
            detail=(
                "Failed to process the uploaded paper: "
                f"{exc}"
            ),
        ) from exc

    finally:

        Path(temp_path).unlink(
            missing_ok=True,
        )

    session = session_manager.create(
        paper_title=result.report["paper"]["title"],
        report=result.report,
        paper=result.paper,
    )

    return {

        "status": "success",

        "feature": "Prerequisite Explorer",

        "session_id": session.session_id,

        "report": result.report,
    }
