"""POST /api/curriculum: one study plan over several analysed papers (see backend/curriculum.py)."""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from backend import curriculum, learner_profile, study_calendar
from backend.api.workflow_result import failure_response, success_body
from backend.prerequisites.study_time_estimator import parse_hours_per_day
from backend.session import session_manager

router = APIRouter(prefix="/api/curriculum", tags=["Curriculum"])


class CurriculumRequest(BaseModel):
    session_ids: list[str]
    profile: str | None = None
    deadline: str | None = None
    hours_per_day: float | None = None
    adapted: bool = True  # schedule the hours adapted to each paper's assessed answers (false: the original plan)
    weekdays: str | None = None
    today: str | None = None
    accept_mastered: list[str] = []  # quiz-mastered concepts (see `mastery_hints` of an earlier answer) the learner chooses to leave out


@router.post("")
def create_curriculum(body: CurriculumRequest):
    """Merge the plans of 2 to 10 analysed papers (`session_ids`, from earlier analyses) into one: shared prerequisites once, what the learner `profile` already
    knows or has studied left out, a paper order and one schedule against `deadline` / `weekdays` / `hours_per_day`. The sessions are only read."""
    ids = [item.strip() for item in body.session_ids if isinstance(item, str)]
    if not 2 <= len(ids) <= curriculum.MAX_PAPERS or len(set(ids)) != len(ids) or "" in ids:
        return failure_response(422, "curriculum", f"`session_ids` must name 2 to {curriculum.MAX_PAPERS} different sessions (got {len(body.session_ids)}).",
                                hint="Analyse each paper first and send the session_id of every one of them, once.")
    sessions = {sid: session_manager.get(sid) for sid in ids}
    missing = [sid for sid, session in sessions.items() if session is None]
    if missing:
        return failure_response(404, "curriculum", "Unknown session" + ("s" if len(missing) > 1 else "") + ": " + ", ".join(missing),
                                hint="Use the session_id of an analysis (GET /api/session lists them); nothing was planned.")
    warnings, profile = [], None
    if body.profile is not None:
        directory = learner_profile.configured_directory()
        path = learner_profile.profile_path(directory, body.profile) if directory else None
        if not directory:
            warnings.append(f"`profile` was ignored: persistent learner profiles are off ({learner_profile.PROFILE_DIR_ENV} is not set).")
        elif path is None:
            return failure_response(422, "curriculum", "Invalid `profile`: a profile name is 1 to 64 letters, digits, hyphens or underscores.", hint="Choose a simple name such as `default`.")
        else:
            profile, problem = learner_profile.load_full(path)
            if problem:
                return failure_response(409, "curriculum", problem, hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    try:
        today = study_calendar.parse_date(body.today, "today") if body.today else datetime.now(timezone.utc).date()
        daily = parse_hours_per_day(body.hours_per_day)
        result = curriculum.build_curriculum([sessions[sid] for sid in ids], profile, today,
                                             study_calendar.parse_date(body.deadline, "deadline") if body.deadline else None, daily,
                                             study_calendar.parse_weekdays(body.weekdays), body.accept_mastered, body.adapted)
    except ValueError as error:  # CalendarError and bad hours are ValueErrors
        return failure_response(422, "curriculum", str(error), hint="Send dates as YYYY-MM-DD, weekdays as mon,tue,..., and hours per day above 0 and at most 24.")
    return success_body("Curriculum", "curriculum", warnings=warnings, **result)
