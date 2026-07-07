from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel

from backend.session import (
    session_manager,
    QuestionManager,
)

router = APIRouter(

    prefix="/api/session",

    tags=["Learning Session"],
)

question_manager = QuestionManager()


class QuestionRequest(BaseModel):

    question: str

    topic: str | None = None


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

    learning_question = question_manager.ask(

        session,

        body.question,

        body.topic,
    )

    return {

        "question_id": learning_question.question_id,

        "status": "received",
    }
