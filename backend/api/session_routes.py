from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel

from backend.session import (
    session_manager,
    TutorMode,
)

from backend.pipeline import (
    InteractiveLearningPipeline,
)

router = APIRouter(

    prefix="/api/session",

    tags=["Learning Session"],
)

pipeline = (
    InteractiveLearningPipeline()
)


class QuestionRequest(BaseModel):

    question: str

    topic: str | None = None

    mode: TutorMode = TutorMode.INTUITION


@router.get("/{session_id}")
def get_session(session_id: str):

    session = session_manager.get(session_id)

    if session is None:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    return {

        "session_id": session.session_id,

        "paper_title": session.paper_title,

        "status": session.status,

        "active_concept": session.active_concept,

        "conversation_history": session.conversation_history,

        "current_context": (

            {
                "concepts": session.current_context.concepts,
                "sections": session.current_context.sections,
                "equations": session.current_context.equations,
            }

            if session.current_context is not None
            else None
        ),
    }


@router.post("/{session_id}/question")
def ask_question(

    session_id: str,

    body: QuestionRequest,
):

    session = session_manager.get(session_id)

    if session is None:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    result = pipeline.answer(

        session=session,

        paper=session.paper,

        question=body.question,

        mode=body.mode,

        topic=body.topic,
    )

    return result
