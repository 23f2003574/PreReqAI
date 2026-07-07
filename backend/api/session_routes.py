from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.session import (
    session_manager,
)

router = APIRouter(

    prefix="/api/session",

    tags=["Learning Session"],
)


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
