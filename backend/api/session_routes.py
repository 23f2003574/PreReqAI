from fastapi import (
    APIRouter,
)
from pydantic import BaseModel

from backend.api.workflow_result import (
    failure_response,
    success_body,
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

    topic = body.topic.strip() if body.topic is not None else None

    if topic:  # a topic must name a concept of this paper; it becomes the session's active concept

        known = {
            concept.name.casefold(): concept.name
            for concept in getattr(session.paper, "concepts", None) or []
        }

        if topic.casefold() not in known:

            return failure_response(
                422,
                "question",
                f"Unknown topic: {body.topic!r}",
                hint="Use one of this paper's concepts: "
                     + (", ".join(known.values()) or "none were detected")
                     + ". Omit `topic` to ask without one.",
            )

        topic = known[topic.casefold()]

    try:

        result = pipeline.answer(

            session=session,

            paper=session.paper,

            question=body.question,

            mode=body.mode,

            topic=topic or None,
        )

    except Exception as exc:  # same envelope as every other failure, never a bare 500

        return failure_response(
            500,
            "question",
            "Failed to answer the question",
            error=exc,
            hint="Try rephrasing the question; if it keeps failing, re-run the analysis to start a new session.",
        )

    # Same success envelope as analysis (status/feature/stage/warnings), so a
    # client checks `status` the same way for every PreReqAI response; the
    # answer's own keys (question, responses, ...) stay at the top level.
    return success_body("Interactive Learning", "answered", **result)
