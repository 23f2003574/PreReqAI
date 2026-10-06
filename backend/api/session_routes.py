from fastapi import (
    APIRouter,
)
from pydantic import BaseModel

from backend.api.workflow_result import (
    failure_response,
)

from backend.session import (
    session_manager,
    TutorMode,
)

from backend.platform import (
    platform,
)

router = APIRouter(

    prefix="/api/session",

    tags=["Learning Session"],
)

pipeline = platform.learning


class QuestionRequest(BaseModel):

    question: str

    topic: str | None = None

    mode: TutorMode = TutorMode.INTUITION


@router.get("/{session_id}")
def get_session(session_id: str):

    session = session_manager.get(session_id)

    if session is None:

        return failure_response(
            404,
            "session_lookup",
            "Session not found",
            hint="Run an analysis first and use the session_id it returns.",
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

        return failure_response(
            404,
            "session_lookup",
            "Session not found",
            hint="Run an analysis first and use the session_id it returns.",
        )

    if not body.question or not body.question.strip():

        return failure_response(
            422,
            "question",
            "Question must be a non-empty string",
            hint="Send a question about the paper in the request body's `question` field.",
        )

    try:

        result = pipeline.answer(

            session=session,

            paper=session.paper,

            question=body.question,

            mode=body.mode,

            topic=body.topic,
        )

    except Exception as exc:  # same envelope as every other failure, never a bare 500

        return failure_response(
            500,
            "question",
            "Failed to answer the question",
            error=exc,
            hint="Try rephrasing the question; if it keeps failing, re-run the analysis to start a new session.",
        )

    return result
