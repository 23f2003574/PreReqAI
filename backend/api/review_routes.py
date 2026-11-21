"""GET /api/review: the learner profile's spaced-review queue (see spaced_review.py)."""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend import learner_profile
from backend.api.workflow_result import failure_response, success_body

router = APIRouter(prefix="/api/review", tags=["Spaced review"])


@router.get("")
def review_queue(profile: str | None = None, limit: int = Query(default=10, ge=1, le=100)):
    """Questions due for review now (most overdue first), the next `limit` upcoming ones and each concept's next due time, from the learner profile
    (`profile`, `default` if omitted). Needs PREREQAI_PROFILE_DIR; an unreadable profile answers 409 and is left untouched."""
    directory = learner_profile.configured_directory()
    if not directory:
        return failure_response(404, "review", f"Spaced review needs a learner profile: {learner_profile.PROFILE_DIR_ENV} is not set.",
                                hint=f"Start the server with {learner_profile.PROFILE_DIR_ENV}=/some/private/dir and analyse papers with a `profile`.")
    path = learner_profile.profile_path(directory, profile)
    if path is None:
        return failure_response(422, "review", "Invalid `profile`: a profile name is 1 to 64 letters, digits, hyphens or underscores.",
                                hint="Choose a simple name such as `default`, or omit `profile`.")
    queue, problem = learner_profile.review_queue(path, upcoming_limit=limit)
    if problem:
        return failure_response(409, "review", problem, hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    return success_body("Spaced Review", "review", profile=path.stem, **queue)


class ReviewGrade(BaseModel):
    question_id: str
    concept: str
    grade: str  # again, hard, good or easy
    profile: str | None = None


@router.post("/grade")
def grade_review(body: ReviewGrade):
    """Record a review answered again, hard, good or easy: the question's own ease and next review time follow from the grade."""
    from backend.tutor.quiz_session import ASKABLE

    directory = learner_profile.configured_directory()
    path = learner_profile.profile_path(directory, body.profile) if directory else None
    if path is None:
        return failure_response(404, "review", "Grading a review needs a learner profile: set the profile directory and a valid profile name.", hint=f"Set {learner_profile.PROFILE_DIR_ENV}.")
    concept, _, number = body.question_id.rpartition(":")
    difficulty = ASKABLE[concept][int(number) - 1]["difficulty"] if concept in ASKABLE and number.isdigit() and 1 <= int(number) <= len(ASKABLE[concept]) else "Medium"
    try:
        entry = learner_profile.record_review(path, body.question_id, body.concept, body.grade, difficulty=difficulty)
    except (learner_profile.ProfileError, OSError) as error:
        return failure_response(422, "review", str(error), hint="Use again, hard, good or easy for a question the profile knows.")
    return success_body("Spaced Review", "review", profile=path.stem, question_id=body.question_id, next_review=entry["due"], interval_hours=entry["interval_hours"], ease=entry["ease"], grade=entry["last_grade"])


@router.get("/schedule")
def review_schedule(profile: str | None = None, cap: int = Query(default=10, ge=1, le=200), days: int = Query(default=30, ge=1, le=365)):
    """The profile's reviews laid out over days, never more than `cap` on a day; overdue work spreads over the first days and what falls beyond `days` is listed as deferred."""
    directory = learner_profile.configured_directory()
    path = learner_profile.profile_path(directory, profile) if directory else None
    if path is None:
        return failure_response(404, "review", "The review schedule needs a learner profile: set the profile directory and a valid profile name.", hint=f"Set {learner_profile.PROFILE_DIR_ENV}.")
    schedule, problem = learner_profile.review_schedule(path, None, cap, days)
    if problem:
        return failure_response(409, "review", problem, hint="Repair or delete the file by hand; PreReqAI never overwrites a profile it cannot read.")
    return success_body("Spaced Review", "review", profile=path.stem, **schedule)
