"""GET /api/review: the learner profile's spaced-review queue (see spaced_review.py)."""
from fastapi import APIRouter, Query

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
