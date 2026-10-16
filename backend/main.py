from backend.python_version import check_python_version

check_python_version()  # before the imports below, which fail obscurely on an old interpreter

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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

def cors_origins() -> list[str]:
    """Origins allowed to call the API from a browser: PREREQAI_CORS_ORIGINS, comma separated (unset or blank: none)."""
    return [origin.strip().rstrip("/") for origin in os.environ.get("PREREQAI_CORS_ORIGINS", "").split(",") if origin.strip()]


if cors_origins():  # off by default: a same-origin or command-line deployment needs no cross-origin access
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

app.include_router(
    prerequisite_router,
)

app.include_router(
    session_router,
)

app.include_router(
    recovery_decision_router,
)


@app.get("/health", tags=["Service"])
def health():
    """Liveness probe for deployments and uptime checks: the server is up, and which release it is."""
    return {"status": "ok", "service": "PreReqAI", "version": __version__}


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
