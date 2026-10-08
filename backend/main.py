from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from backend.api.workflow_result import (
    failure_response,
)

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
)

from backend.api.recovery_decision_routes import (
    router as recovery_decision_router,
)

from backend.version import __version__
from backend.platform import (  # noqa: F401  (kept as backend.main.platform)
    platform,
)

app = FastAPI(
    title="PreReqAI",
    version=__version__,
)

app.include_router(
    prerequisite_router,
)

app.include_router(
    session_router,
)

app.include_router(
    recovery_decision_router,
)


def _field(location) -> str:
    """("body", "mode") -> "mode": the request field a client actually sent."""
    parts = [str(part) for part in location if part not in ("body", "query", "path")]
    return ".".join(parts) or "request body"


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    """A malformed request (missing upload, unknown tutor mode, missing
    question...) gets the same failure envelope as every other PreReqAI
    failure -- naming each bad field and what it should be -- instead of
    FastAPI's raw validation list. The status code stays 422."""
    problems = [f"{_field(error['loc'])}: {error['msg']}" for error in exc.errors()]
    return failure_response(
        422, "input", "Invalid request: " + "; ".join(problems),
        hint="Fix the fields named above; see /docs for each endpoint's expected request.",
    )
