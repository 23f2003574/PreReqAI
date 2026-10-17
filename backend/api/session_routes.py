from fastapi import (
    APIRouter,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.study_plan_markdown import plan_markdown

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


# Far above any real question; it keeps one request from bloating the stored conversation (and its saved file).
MAX_QUESTION_CHARS = 2000


class QuestionRequest(BaseModel):

    question: str

    topic: str | None = None

    mode: TutorMode = TutorMode.INTUITION


@router.get("")
def list_sessions():
    """The sessions this server knows (newest first), so a client that lost an id can find its analysis again."""

    return {
        "status": "success",
        "sessions": [
            {
                "session_id": session.session_id,
                "paper_title": session.paper_title,
                "created_at": getattr(session, "created_at", None),
                "readiness": (session.report.get("readiness") or {}).get("status"),
            }
            for session in session_manager.list()
        ],
    }


def session_not_found(session_id: str):
    """404 for an unknown session; a saved file that cannot be read says so instead of looking like a typo."""

    if session_manager.is_unreadable(session_id):

        return failure_response(
            404,
            "session_lookup",
            "Session could not be restored",
            hint="Its saved file is unreadable (corrupt or from another version). "
            "DELETE /api/session/{session_id} clears it; then run the analysis again.".replace("{session_id}", session_id),
        )

    return failure_response(
        404,
        "session_lookup",
        "Session not found",
        hint="Run an analysis first and use the session_id it returns.",
    )


def _next_resources(report):
    """Study links for the planned concepts not yet studied, in study order (same list as `analyze --resources`)."""

    done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
    order = {step["concept"]: step["step"] for step in report.get("learning_plan", [])}

    return sorted(
        (item for item in report.get("learning_resources", []) if item["concept"] not in done),
        key=lambda item: order.get(item["concept"], len(order) + 1),
    )


@router.get("/{session_id}")
def get_session(session_id: str):

    session = session_manager.get(session_id)

    if session is None:

        return session_not_found(session_id)

    return {

        "session_id": session.session_id,

        "paper_title": session.paper_title,

        "status": session.status,

        "study_progress": session.report.get("study_progress", []),

        "readiness": session.report.get("readiness"),

        "next_resources": _next_resources(session.report),

        "prerequisite_tree": session.report.get("prerequisite_tree", []),

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


@router.get("/{session_id}/plan")
def get_study_plan(session_id: str):
    """The session's study plan as a Markdown checklist, with progress ticked (same text as `analyze --plan-file`)."""

    session = session_manager.get(session_id)

    if session is None:

        return session_not_found(session_id)

    return PlainTextResponse(plan_markdown(session.report), media_type="text/markdown; charset=utf-8")


@router.delete("/{session_id}")
def delete_session(session_id: str):
    """Delete a session and its saved file (when PREREQAI_SESSION_DIR is set); its id is unknown afterwards."""

    if not session_manager.delete(session_id):

        return failure_response(
            404,
            "session_lookup",
            "Session not found",
            hint="Run an analysis first and use the session_id it returns.",
        )

    return {"status": "success", "session_id": session_id, "deleted": True}


@router.post("/{session_id}/question")
def ask_question(

    session_id: str,

    body: QuestionRequest,
):

    session = session_manager.get(session_id)

    if session is None:

        return session_not_found(session_id)

    if not body.question or not body.question.strip():

        return failure_response(
            422,
            "question",
            "Question must be a non-empty string",
            hint="Send a question about the paper in the request body's `question` field.",
        )

    if len(body.question) > MAX_QUESTION_CHARS:

        return failure_response(
            422,
            "question",
            f"Question is too long ({len(body.question)} characters; the limit is {MAX_QUESTION_CHARS})",
            hint="Ask about one thing at a time with a shorter question.",
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

    session_manager.save(session)

    # Same success envelope as analysis (status/feature/stage/warnings), so a
    # client checks `status` the same way for every PreReqAI response; the
    # answer's own keys (question, responses, ...) stay at the top level.
    placeholder = any(
        "tutoring model has not yet been configured" in str(getattr(response, "answer", ""))
        for response in result.get("responses", [])
    )

    responses = result.get("responses", [])
    built_in = bool(responses) and not placeholder and any(
        getattr(response, "confidence", 0) for response in responses
    )

    if placeholder:
        warnings = ["No tutoring model is configured in this release: the answer is a placeholder; "
                    "supporting_concepts and supporting_sections show where the paper covers the question."]
    elif built_in:
        warnings = ["No tutoring model is configured in this release: answers are the built-in definitions "
                    "prerequisite reasons and study plan from the analysis, not generated explanations."]
    else:
        warnings = []

    return success_body(
        "Interactive Learning", "answered",
        warnings=warnings,
        **result,
    )
