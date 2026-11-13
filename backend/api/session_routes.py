from fastapi import (
    APIRouter,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.platform.prereqai_platform import _concept_key
from backend.study_plan_markdown import plan_markdown, studied_concepts
from backend.tutor import quiz_session
from backend.tutor.rule_based_tutor import ANSWERABLE_HINT

from backend.api.workflow_result import (
    REQUEST_FAILURES,
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
    responses=REQUEST_FAILURES,
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
            *session_manager.summaries()
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

    hint = "Run an analysis first and use the session_id it returns."

    if session_manager._directory() is None:  # the usual reason a once-valid id is gone: the server restarted

        hint += (" Sessions are kept in memory only and are lost when the server restarts; "
                 "set PREREQAI_SESSION_DIR to keep them across restarts.")

    return failure_response(
        404,
        "session_lookup",
        "Session not found",
        hint=hint,
    )


def _next_resources(report):
    """Study links for the planned concepts not yet studied, in study order (same list as `analyze --resources`)."""

    done = studied_concepts(report)
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

        "study_time": session.report.get("study_time"),

        "quiz_progress": quiz_session.progress(session),

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


class MarkdownResponse(PlainTextResponse):
    """Markdown text: declared as text/markdown in the OpenAPI document (a generated client must not parse it as JSON)."""

    media_type = "text/markdown"


_FAILURE_JSON = {"application/json": {"schema": {"$ref": "#/components/schemas/FailureEnvelope"}}}


# Failures stay the JSON failure envelope: only the success body is Markdown.
@router.get("/{session_id}/plan", response_class=MarkdownResponse,
            responses={404: {"description": "Unknown session", "content": _FAILURE_JSON},
                       422: {"description": "Invalid request", "content": _FAILURE_JSON}})
def get_study_plan(session_id: str):
    """The session's study plan as a Markdown checklist, with progress ticked (same text as `analyze --plan-file`)."""

    session = session_manager.get(session_id)

    if session is None:

        return session_not_found(session_id)

    return MarkdownResponse(plan_markdown(session.report))


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


def resolve_topic(session, topic):
    """(concept name, None) for a topic naming one of the paper's concepts or study-plan prerequisites (ignoring case, whitespace, hyphens and underscores, as `--known` does); (None, None) when no
    topic is given; (None, hint) when it names no concept. Shared by POST /question and `prerequisites ask --topic`."""

    if topic is None:

        return None, None

    topic = topic.strip()

    if not topic:  # a blank value is a mistake (an unset variable), not "no topic": the CLI refuses a blank --topic too

        return None, "`topic` is blank. Name one of this paper's concepts or study-plan topics, or omit `topic` to ask without one."

    known = {
        _concept_key(concept.name): concept.name
        for concept in getattr(session.paper, "concepts", None) or []
    }

    # the study plan lists prerequisites the paper never names (Probability, Calculus...): the learner studies and asks about them too
    for item in getattr(session.paper, "study_progress", None) or []:

        known.setdefault(_concept_key(item.concept), item.concept)

    if _concept_key(topic) not in known:

        return None, ("Use one of this paper's concepts or study-plan topics: "
                      + (", ".join(known.values()) or "none were detected")
                      + ". Omit `topic` to ask without one.")

    return known[_concept_key(topic)], None


class QuizReveal(BaseModel):

    question_id: str


class QuizOutcome(BaseModel):

    question_id: str

    outcome: str


_QUIZ_STATUS = {"unsupported": 422, "unknown": 404, "state": 409, "outcome": 422}


def _quiz(session_id, action, saves=True):
    """Run one quiz operation on the session and save it; a refused one is a failure body with a status that says why."""
    session = session_manager.get(session_id)

    if session is None:

        return session_not_found(session_id)

    try:

        result = action(session)

    except quiz_session.QuizError as error:

        return failure_response(_QUIZ_STATUS[error.kind], "quiz", str(error), hint=error.hint)

    if saves:

        session.report["quiz_progress"] = quiz_session.progress(session)  # the session's report keeps the latest mastery summary

        session_manager.save(session)

    return success_body("Interactive Quiz", "quiz", session_id=session_id, **result)


@router.get("/{session_id}/quiz/question")
def quiz_question(session_id: str, concept: str | None = None):
    """One practice question without its answer: for `concept`, or the paper's concept that needs practice most."""
    return _quiz(session_id, lambda session: quiz_session.next_question(session, concept))


@router.post("/{session_id}/quiz/reveal")
def quiz_reveal(session_id: str, body: QuizReveal):
    """The answer to a question that was served."""
    return _quiz(session_id, lambda session: quiz_session.reveal(session, body.question_id))


@router.post("/{session_id}/quiz/outcome")
def quiz_outcome(session_id: str, body: QuizOutcome):
    """Record `knew` or `missed` for a served question (once); answers with the updated per-concept mastery."""
    return _quiz(session_id, lambda session: {"progress": quiz_session.record(session, body.question_id, body.outcome)})


@router.get("/{session_id}/quiz/progress")
def quiz_progress(session_id: str):
    """Attempts and mastery per concept."""
    return _quiz(session_id, lambda session: {"progress": quiz_session.progress(session)}, saves=False)


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

    topic, problem = resolve_topic(session, body.topic)

    if problem:

        return failure_response(422, "question", f"Unknown topic: {body.topic!r}", hint=problem)

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
                    "supporting_concepts and supporting_sections show where the paper covers the question. "
                    + ANSWERABLE_HINT]
    elif built_in:
        warnings = ["No tutoring model is configured in this release: answers are the built-in definitions "
                    "prerequisite reasons and study plan from the analysis, not generated explanations."]
    else:
        warnings = []

    if not session_manager.last_save_ok:  # same wording the progress endpoints use when a change cannot be written
        warnings.append("This change could not be saved to PREREQAI_SESSION_DIR, so it will not survive a server restart; "
                        "check that the directory exists and is writable.")

    return success_body(
        "Interactive Learning", "answered",
        warnings=warnings,
        **result,
    )
