from fastapi import (
    APIRouter,
    Query,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.platform.prereqai_platform import _concept_key
from backend.prerequisites.personalised_plan import build_plan
from backend.prerequisites.prerequisite_paths import build_paths
from backend.study_plan_markdown import plan_markdown, studied_concepts
from backend.tutor import diagnostic, paper_quiz as paper_quiz_module, quiz_session
from backend.tutor.tutor_provider import TutorConfig
from backend.tutor.rule_based_tutor import ANSWERABLE_HINT, EXTRACTIVE_PREFIX

from backend.api.workflow_result import (
    REQUEST_FAILURES,
    failure_response,
    success_body,
)

from datetime import datetime, time, timezone

from backend import adaptive_plan, learner_profile, study_calendar
from backend import learning_services
from backend.prerequisites.study_time_estimator import parse_hours_per_day
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

    sessions = [*session_manager.summaries()]  # first: it is what finds the unreadable files below

    return {
        "status": "success",
        "sessions": sessions,
        "unreadable": session_manager.unreadable_ids(),  # saved files that cannot be read; DELETE /api/session/{id} removes one
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

        "plan_start": session.plan_start_date().isoformat(),
        "study_progress": session.report.get("study_progress", []),

        "readiness": session.report.get("readiness"),

        "next_resources": _next_resources(session.report),

        "study_time": session.report.get("study_time"),

        "quiz_progress": quiz_session.progress(session),

        "suggest_known": _suggestions(session),

        "quiz_topics": quiz_session.topics(session),

        "quiz_pending": quiz_session.pending(session),

        "prerequisite_tree": session.report.get("prerequisite_tree", []),
        "study_paths": build_paths(session.paper),
        **({"personalised_plan": build_plan(session.paper, session.report["personalised_plan"]["sources"])} if session.report.get("personalised_plan") else {}),  # built from the session's current progress, so it follows studied and known concepts

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

    return MarkdownResponse(plan_markdown(session.report, session.plan_start_date().isoformat()))


@router.get("/{session_id}/reading-list")
def reading_list(session_id: str, limit: int = Query(default=10, ge=1, le=50)):
    """The works this paper cites that are most worth reading first (see backend/reading_list.py): ranked by where and how often they are cited, with the concepts
    they support and the reason. `source` of a resolvable item can be sent to POST /api/prerequisites/analyze to read that paper next; nothing is fetched here."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    return success_body("Prerequisite Reading List", "reading_list", session_id=session_id, reading_list=learning_services.reading_list(session, limit))


@router.get("/{session_id}/evidence")
def concept_evidence(session_id: str, concept: str | None = None):
    """The paper's own sentences behind each detected concept, with page, section and a passage id (see backend/evidence.py); only `concept` when given."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    return success_body("Concept Evidence", "evidence", session_id=session_id, evidence=learning_services.evidence(session, concept))


@router.post("/{session_id}/plan-start")
def set_plan_start(session_id: str, date: str | None = None):
    """Start the plan over: its start becomes `date` (YYYY-MM-DD, default today, UTC), so days before it are never reported as missed. Studied concepts stay studied."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    try:
        day = study_calendar.parse_date(date, "date") if date else datetime.now(timezone.utc).date()
    except study_calendar.CalendarError as error:
        return failure_response(422, "calendar", str(error), hint="Send a date as YYYY-MM-DD.")
    session.plan_start = day.isoformat()
    session_manager.save(session)
    return success_body("Study Calendar", "calendar", session_id=session_id, plan_start=session.plan_start)


class CalendarMarkdown(PlainTextResponse):
    media_type = "text/calendar"


def _calendar(session_id, deadline, hours_per_day, weekdays, today, start, timezone_name, start_time):
    """(session, calendar, timezone name, start time) for the calendar endpoints, or a failure response. Hours default to the session's own daily hours."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    try:
        report = session.report
        daily = parse_hours_per_day(hours_per_day if hours_per_day is not None else (report.get("study_time") or {}).get("daily_hours"))
        today_date = study_calendar.parse_date(today, "today") if today else datetime.now(timezone.utc).date()
        steps, importance, studied = study_calendar.plan_inputs(report)
        begun = study_calendar.parse_date(start, "start") if start else min(session.plan_start_date(), today_date)  # the plan's own start unless the caller names one
        calendar = study_calendar.build_calendar(
            steps, importance, daily, today_date, study_calendar.parse_weekdays(weekdays),
            study_calendar.parse_date(deadline, "deadline") if deadline else None, begun, studied, study_calendar.planned_steps(report))
        calendar["plan_start"] = begun.isoformat()
        hours, _, minutes = (start_time or "09:00").partition(":")
        begin = time(int(hours), int(minutes or 0))
    except (ValueError, study_calendar.CalendarError) as error:  # CalendarError is a ValueError; so are bad hours and bad times
        return failure_response(422, "calendar", str(error), hint="Send dates as YYYY-MM-DD, weekdays as mon,tue,..., hours per day above 0 and at most 24, start_time as HH:MM.")
    return session, calendar, timezone_name or "UTC", begin


@router.get("/{session_id}/calendar")
def study_calendar_json(session_id: str, deadline: str | None = None, hours_per_day: float | None = None, weekdays: str | None = None,
                        today: str | None = None, start: str | None = None):
    """The remaining study plan on real dates: `deadline` (YYYY-MM-DD) adds a feasibility verdict (achievable, or the extra daily hours needed and the date you
    would finish), `weekdays` (mon,tue,...) limits the study days, `today` is the first day work can happen (default: today, UTC), and `start` the day the plan
    began, so work planned for earlier days that is still not done is listed as `missed_sessions` and laid out again from `today`. Studied concepts are not scheduled."""
    found = _calendar(session_id, deadline, hours_per_day, weekdays, today, start, None, None)
    if not isinstance(found, tuple):
        return found
    return success_body("Study Calendar", "calendar", session_id=session_id, **found[1])


@router.get("/{session_id}/calendar.ics", response_class=CalendarMarkdown,
            responses={404: {"description": "Unknown session", "content": _FAILURE_JSON}, 422: {"description": "Invalid request", "content": _FAILURE_JSON}})
def study_calendar_ics(session_id: str, deadline: str | None = None, hours_per_day: float | None = None, weekdays: str | None = None,
                       today: str | None = None, start: str | None = None, timezone: str = "UTC", start_time: str = "09:00"):
    """The same calendar as an iCalendar file: one event per scheduled item, back to back from `start_time` local time in `timezone` (an IANA name)."""
    found = _calendar(session_id, deadline, hours_per_day, weekdays, today, start, timezone, start_time)
    if not isinstance(found, tuple):
        return found
    try:
        text = study_calendar.to_ics(found[1], title=f"Study plan: {session_manager.get(session_id).paper_title}", timezone_name=found[2], start_at=found[3])
    except study_calendar.CalendarError as error:
        return failure_response(422, "calendar", str(error), hint="Use an IANA time zone name such as UTC or Europe/Berlin.")
    return CalendarMarkdown(text, headers={"Content-Disposition": 'attachment; filename="study-plan.ics"'})


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


class PaperQuizReveal(BaseModel):

    question_id: str

    attempt: str | None = None  # what the learner typed in the blank, if anything: only compared with the answer, never required


class QuizOutcome(BaseModel):

    question_id: str

    outcome: str


class AdaptiveOverride(BaseModel):

    concept: str

    action: str  # "reject": keep the original hours; "restore": adapt again


class DiagnosticAnswer(BaseModel):

    question_id: str

    choice: int  # the position of the option picked, as served

    confidence: str  # low, medium or high


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


@router.get("/{session_id}/diagnostic/question")
def diagnostic_question(session_id: str, concept: str | None = None):
    """A practice question with four options and no answer, graded by the system when answered (POST /diagnostic/answer)."""
    return _quiz(session_id, lambda session: diagnostic.serve(session, concept))


@router.post("/{session_id}/diagnostic/answer")
def diagnostic_answer(session_id: str, body: DiagnosticAnswer):
    """Check the chosen option, record it as an assessed answer with the learner's confidence, and answer with the verdict, the explanation and the updated progress."""
    def act(session):
        verdict = diagnostic.grade(session, body.question_id, body.choice, body.confidence)
        review = _remember_outcome(session)
        return {"verdict": verdict, "progress": quiz_session.progress(session), "assessed": diagnostic.assessed_summary(session), **({"review": review} if review else {})}

    return _quiz(session_id, act)


@router.get("/{session_id}/adaptive-plan/assessment")
def adaptive_assessment(session_id: str, limit: int = 6):
    """A short pre-assessment: one diagnostic question (with options, no answer) for each step of the plan that has fewer than 3 assessed answers, at most `limit` (1 to 12) of them."""
    def act(session):
        have = diagnostic.assessed_summary(session)
        wanted = [step["concept"] for step in session.report.get("learning_plan", []) if step["concept"] in quiz_session.ASKABLE and have.get(step["concept"], {}).get("graded", 0) < adaptive_plan.MIN_GRADED]
        questions = [diagnostic.serve(session, name) for name in wanted[:max(1, min(limit, 12))]]
        return {"questions": questions, "note": "Answer each with how sure you are; then GET /adaptive-plan shows what changes." if questions else "Every step already has enough assessed answers or no questions."}

    return _quiz(session_id, act)


@router.get("/{session_id}/adaptive-plan")
def adaptive_plan_view(session_id: str, deadline: str | None = None, hours_per_day: float = 3.0, today: str | None = None):
    """The plan adapted to the learner's assessed answers: each change with its reason, the remediation lists, hours before and after, and (with a deadline) feasibility before and after."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    calendar = None
    try:
        if deadline:
            day = study_calendar.parse_date(today, "today") if today else datetime.now(timezone.utc).date()
            calendar = {"today": day, "deadline": study_calendar.parse_date(deadline, "deadline"), "daily_hours": hours_per_day}
        result = adaptive_plan.propose(session.report, session.quiz_attempts, session.report.get("adaptive_overrides", {}), calendar)
    except study_calendar.CalendarError as error:
        return failure_response(422, "adaptive_plan", str(error), hint="Send dates as YYYY-MM-DD and hours per day above 0 and at most 24.")
    return success_body("Adaptive Plan", "adaptive_plan", session_id=session_id, **result)


@router.post("/{session_id}/adaptive-plan/override")
def adaptive_override(session_id: str, body: AdaptiveOverride):
    """Reverse (action "reject") or bring back (action "restore") the adaptation of one step; the choice is saved with the session."""
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    if body.action not in ("reject", "restore"):
        return failure_response(422, "adaptive_plan", f"action must be 'reject' or 'restore', not {body.action!r}.", hint="Send {\"concept\": ..., \"action\": \"reject\"}.")
    if body.concept not in {step["concept"] for step in session.report.get("learning_plan", [])}:
        return failure_response(404, "adaptive_plan", f"{body.concept!r} is not a step of this plan.", hint="Use a concept from the plan.")
    overrides = dict(session.report.get("adaptive_overrides", {}))
    if body.action == "reject":
        overrides[body.concept] = "reject"
    else:
        overrides.pop(body.concept, None)
    session.report["adaptive_overrides"] = overrides
    session_manager.save(session)
    return success_body("Adaptive Plan", "adaptive_plan", session_id=session_id, overrides=overrides)


@router.post("/{session_id}/quiz/reveal")
def quiz_reveal(session_id: str, body: QuizReveal):
    """The answer to a question that was served."""
    return _quiz(session_id, lambda session: quiz_session.reveal(session, body.question_id))


@router.get("/{session_id}/paper-quiz")
def paper_quiz(session_id: str, kinds: str = "cloze"):
    """Questions about this paper made from its own verified sentences (without answers), separate from the global concept questions. kinds=cloze (default): fill in the blank;
    kinds=comprehension: true/false claims, equation-to-subject questions and method-step ordering."""
    def act(session):
        if kinds not in ("cloze", "comprehension"):
            raise quiz_session.QuizError("unsupported", f"kinds must be 'cloze' or 'comprehension', not {kinds!r}.", "Use /paper-quiz?kinds=comprehension.")
        questions = paper_quiz_module.build(session) if kinds == "cloze" else paper_quiz_module.build_comprehension(session)
        return {"questions": [paper_quiz_module.public(q, n, len(questions)) for n, q in enumerate(questions, start=1)],
                "note": ("Each question comes from a sentence (or equation) the paper really contains; revealing shows it, its page and its section." if kinds == "comprehension" else
                         "Each blank is a term from a sentence the paper really contains; revealing shows the sentence, its page and its section.") if questions else
                        "This paper has no passage that makes a good question of this kind."}

    return _quiz(session_id, act, saves=False)


@router.post("/{session_id}/paper-quiz/reveal")
def paper_quiz_reveal(session_id: str, body: PaperQuizReveal):
    """The answer to a paper question, with the exact quotation, its page and section; `attempt` (optional) is compared with the answer."""
    def act(session):
        _, question = paper_quiz_module.find(session, body.question_id)
        if question is None:
            raise quiz_session.QuizError("unknown", f"There is no paper question {body.question_id!r}.", "Use a question_id from GET /paper-quiz.")
        session.quiz_pending[question["question_id"]] = {"revealed": True}
        found = {"question_id": question["question_id"], "concept": question["concept"], "answer": question["answer"], "quotation": question["quotation"],
                 "page_number": question["page_number"], "section": question["section"]}
        return {**found, **({"attempt_correct": paper_quiz_module.check(question, body.attempt)} if body.attempt is not None else {})}

    return _quiz(session_id, act)


@router.post("/{session_id}/paper-quiz/outcome")
def paper_quiz_outcome(session_id: str, body: QuizOutcome):
    """Record `knew` or `missed` for a paper question that was revealed: it counts toward the concept's mastery and, with a learner profile, enters spaced review."""
    def act(session):
        _, question = paper_quiz_module.find(session, body.question_id)
        if question is None:
            raise quiz_session.QuizError("unknown", f"There is no paper question {body.question_id!r}.", "Use a question_id from GET /paper-quiz.")
        if body.outcome not in quiz_session.OUTCOMES:
            raise quiz_session.QuizError("outcome", f"outcome must be 'knew' or 'missed', not {body.outcome!r}.", "Send {\"outcome\": \"knew\"} or {\"outcome\": \"missed\"}.")
        state = session.quiz_pending.pop(question["question_id"], None)
        if state is None:
            raise quiz_session.QuizError("state", f"No outcome is awaited for {body.question_id!r}: reveal the question first, and answer it once.", "POST /paper-quiz/reveal, then record the outcome.")
        session.quiz_attempts.append({"question_id": question["question_id"], "concept": question["concept"], "outcome": body.outcome, "revealed": True, "kind": "paper"})
        review = _remember_outcome(session)
        return {"progress": quiz_session.progress(session), "suggest_known": _suggestions(session), **({"review": review} if review else {})}

    return _quiz(session_id, act)


@router.post("/{session_id}/quiz/outcome")
def quiz_outcome(session_id: str, body: QuizOutcome):
    """Record `knew` or `missed` for a served question (once); answers with the updated per-concept mastery."""
    def act(session):
        result = {"progress": quiz_session.record(session, body.question_id, body.outcome),
                  "suggest_known": _suggestions(session), "topics": quiz_session.topics(session)}  # offered, never applied
        review = _remember_outcome(session)
        return {**result, **({"review": review} if review else {})}

    return _quiz(session_id, act)


def _suggestions(session):
    """The "you may already know this" suggestions of a session: from its own quiz answers and from the mastery its learner profile holds from earlier sessions and papers, less
    those the learner declined. Offered only; the plan is never changed by them."""
    mastered = {}
    directory = learner_profile.configured_directory()
    path = learner_profile.profile_path(directory, session.profile) if directory and getattr(session, "profile", None) else None
    if path is not None:
        profile, problem = learner_profile.load_full(path)
        mastered = {} if problem else learner_profile.mastered(profile["quiz"])
    return quiz_session.known_suggestions(session, mastered, getattr(session, "dismissed_suggestions", []))


@router.post("/{session_id}/suggestions/dismiss")
def dismiss_suggestion(session_id: str, concept: str):
    """Decline the suggestion that `concept` is already known: it is not offered again for this session (DELETE brings it back). The concept stays in the plan either way."""
    return _dismissal(session_id, concept, True)


@router.delete("/{session_id}/suggestions/dismiss")
def restore_suggestion(session_id: str, concept: str):
    return _dismissal(session_id, concept, False)


def _dismissal(session_id, concept, dismissed):
    session = session_manager.get(session_id)
    if session is None:
        return session_not_found(session_id)
    names = {_concept_key(item.concept): item.concept for item in getattr(session.paper, "study_progress", [])}
    name = names.get(_concept_key(concept))
    if name is None:
        return failure_response(422, "suggestions", f"{concept!r} is not in this session's study plan.", hint="Use a concept name from the plan.")
    current = [item for item in getattr(session, "dismissed_suggestions", []) if item != name]
    session.dismissed_suggestions = [*current, name] if dismissed else current
    session_manager.save(session)
    return success_body("Suggestions", "suggestions", session_id=session_id, concept=name, dismissed=dismissed, suggest_known=_suggestions(session))


def _remember_outcome(session):
    """Keep the answer just recorded in the session's learner profile, with its next review time; None when the session has no profile. A profile
    that cannot be written never fails the quiz: the answer is still recorded in the session and the result says it was not remembered."""
    directory = learner_profile.configured_directory()
    path = learner_profile.profile_path(directory, session.profile) if directory and getattr(session, "profile", None) else None
    if path is None:
        return None
    attempt = session.quiz_attempts[-1]
    try:
        graded = {"correct": attempt["correct"], "confidence": attempt["confidence"]} if attempt.get("graded") else None
        entry = learner_profile.record_quiz(path, attempt["question_id"], attempt["concept"], attempt["outcome"], graded=graded)
    except (learner_profile.ProfileError, OSError) as error:
        return {"saved": False, "warning": f"this answer was not saved to your learner profile: {error}"}
    return {"saved": True, "profile": session.profile, "question_id": attempt["question_id"], "next_review": entry["due"], "interval_hours": entry["interval_hours"]}


@router.get("/{session_id}/quiz/progress")
def quiz_progress(session_id: str):
    """Attempts and mastery per concept."""
    return _quiz(session_id, lambda session: {"progress": quiz_session.progress(session), "suggest_known": _suggestions(session),
                                               "topics": quiz_session.topics(session)}, saves=False)


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
    generated = [response.provider for response in responses if str(getattr(response, "provider", "")).startswith("gemini")]
    built_in = bool(responses) and not placeholder and not generated and any(
        getattr(response, "confidence", 0) for response in responses
    )

    if placeholder:
        warnings = ["No tutoring model is configured in this release: the answer is a placeholder; "
                    "supporting_concepts and supporting_sections show where the paper covers the question. "
                    + ANSWERABLE_HINT]
    elif any(str(getattr(response, "answer", "")).startswith(EXTRACTIVE_PREFIX) for response in responses):
        warnings = ["No tutoring model is configured in this release: this answer quotes passages of the paper that match your question; "
                    "the quotations are the paper's own words and are not an explanation or a check of the paper's claims."]
    elif built_in:
        warnings = ["No tutoring model is configured in this release: answers are the built-in definitions "
                    "prerequisite reasons and study plan from the analysis, not generated explanations."]
    elif generated:
        warnings = [f"This answer was generated by {generated[0]} (an external AI service): it can contain mistakes, and your question with short "
                    "excerpts of the paper were sent to Google to produce it. Check it against the paper."]
    else:
        warnings = []

    for response in responses:  # why the built-in tutor answered when a model tutor was configured but could not (never hidden)
        warnings.extend(note for note in getattr(response, "notes", []) if note not in warnings)

    problem = TutorConfig.from_env().problem  # a mistyped PREREQAI_TUTOR_PROVIDER is told to the learner, not silently ignored
    if problem and problem not in warnings:
        warnings.append(problem)

    if not session_manager.last_save_ok:  # same wording the progress endpoints use when a change cannot be written
        warnings.append("This change could not be saved to PREREQAI_SESSION_DIR, so it will not survive a server restart; "
                        "check that the directory exists and is writable.")

    return success_body(
        "Interactive Learning", "answered",
        warnings=warnings,
        **result,
    )
