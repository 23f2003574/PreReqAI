from backend.python_version import check_python_version

check_python_version()  # before the imports below, which fail obscurely on an old interpreter

import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.workflow_result import (
    failure_response,
)

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
)

from backend.api.curriculum_routes import (
    router as curriculum_router,
)

from backend.api.profile_routes import (
    router as profile_router,
)

from backend.api.review_routes import (
    router as review_router,
)

from backend.api.recovery_decision_routes import (
    router as recovery_decision_router,
)

from backend.api.custom_concept_routes import router as custom_concept_router
from backend.api.web_routes import (
    router as web_router,
)

from backend.version import __version__
from backend.platform import (  # noqa: F401  (kept as backend.main.platform)
    platform,
)

# The HTTP server writes failed-analysis log lines (see PreReqAIPlatform._log_unsuccessful) to stderr; the CLI does not.
_analysis_log = logging.getLogger("prereqai.analysis")
if not any(isinstance(h, logging.StreamHandler) for h in _analysis_log.handlers):
    _analysis_log.addHandler(logging.StreamHandler())

@asynccontextmanager
async def _lifespan(_app):
    from backend.api_auth import warn_if_exposed

    warn_if_exposed()  # a warning when the server listens beyond this computer with no PREREQAI_API_TOKEN
    yield


app = FastAPI(
    title="PreReqAI",
    version=__version__,
    lifespan=_lifespan,
)

def cors_origins() -> list[str]:
    """Origins allowed to call the API from a browser: PREREQAI_CORS_ORIGINS, comma separated (unset or blank: none)."""
    return [origin.strip().rstrip("/") for origin in os.environ.get("PREREQAI_CORS_ORIGINS", "").split(",") if origin.strip()]


if cors_origins():  # off by default: a same-origin or command-line deployment needs no cross-origin access
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])

from backend.security import LocalSecurityMiddleware  # noqa: E402

from backend.api_auth import ApiTokenMiddleware  # noqa: E402
from backend.observability import EVENT_LOGGER, RequestIdMiddleware  # noqa: E402

_events_log = logging.getLogger(EVENT_LOGGER)
if not any(isinstance(h, logging.StreamHandler) for h in _events_log.handlers):
    _events_log.addHandler(logging.StreamHandler())  # one JSON line per event on stderr; PREREQAI_LOG_LEVEL-style control is the logging configuration's job
    _events_log.setLevel(logging.INFO)

app.add_middleware(ApiTokenMiddleware)  # PREREQAI_API_TOKEN: bearer token for /api/ (off when unset; see backend/api_auth.py)
app.add_middleware(RequestIdMiddleware)  # outermost but one: every refusal, including a security or token refusal, carries a request id and is logged
app.add_middleware(LocalSecurityMiddleware)  # added last, so it runs first: Host, Origin and content-type checks and the security headers (see backend/security.py)

app.include_router(
    prerequisite_router,
)

app.include_router(
    session_router,
)

app.include_router(
    profile_router,
)

app.include_router(
    review_router,
)

app.include_router(
    curriculum_router,
)

app.include_router(
    recovery_decision_router,
)

app.include_router(
    custom_concept_router,
)

app.include_router(
    web_router,
)


@app.get("/health", tags=["Service"])
def health():
    """Liveness probe for deployments and uptime checks: the server is up, which release it is, and how many of its analysis slots (see backend/analysis_slots.py, shared by every worker on this computer) are in use,
    so an operator can see saturation before clients start getting 503. `warnings` appears only when a limit or throttle setting is set to something unusable and its default is being used instead."""
    from backend import analysis_slots

    try:
        analysis = {"limit": analysis_slots.limit(), "active": analysis_slots.active()}
    except OSError:  # the slot folder is unusable: the server is still up
        analysis = {"limit": analysis_slots.limit(), "active": None}
    from backend import api_auth

    warnings = [message for message in (analysis_slots.misconfiguration(), *api_auth.misconfiguration()) if message]
    return {"status": "ok", "service": "PreReqAI", "version": __version__, "analysis": analysis, **({"warnings": warnings} if warnings else {})}


def _field(location) -> str:
    """("body", "mode") -> "mode": the request field a client actually sent."""
    parts = [str(part) for part in location if part not in ("body", "query", "path")]
    return ".".join(parts) or "request body"


def _problem(error) -> str:
    """One validation error as text. A body that is not valid JSON locates the error by character position, which `_field` would
    print as a bare number ("1: JSON decode error"): name the body and say what the number is."""
    if error.get("type") == "json_invalid":
        position = error["loc"][-1] if error["loc"] and isinstance(error["loc"][-1], int) else None
        return f"request body: {error['msg']}" + (f" (at character {position})" if position is not None else "")
    return f"{_field(error['loc'])}: {error['msg']}"


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    """An unknown path (404) or a wrong method (405) gets the failure envelope too, so a caller can always read
    `status`, `detail` and `hint` instead of FastAPI's bare {"detail": ...}. `detail` and the headers (Allow) are unchanged."""
    response = failure_response(
        exc.status_code, "routing", str(exc.detail),
        hint="Check the path and HTTP method; see /docs for the endpoints this service offers.",
    )
    response.headers.update(exc.headers or {})
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """An error no route anticipated (a bug, a failed rebuild) gets the failure envelope too, naming the underlying error,
    instead of the server's bare plain-text "Internal Server Error" that a client cannot read `status` from."""
    logging.getLogger(__name__).error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return failure_response(
        500, "server", "The request failed unexpectedly", error=exc,
        hint="Retry the request; if it keeps failing, report it with the error above.",
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    """A malformed request (missing upload, unknown tutor mode, missing
    question...) gets the same failure envelope as every other PreReqAI
    failure -- naming each bad field and what it should be -- instead of
    FastAPI's raw validation list. The status code stays 422."""
    problems = [_problem(error) for error in exc.errors()]
    return failure_response(
        422, "input", "Invalid request: " + "; ".join(problems),
        hint="Fix the fields named above; see /docs for each endpoint's expected request.",
    )


# The routers declare 404 "Unknown session" for every route they hold, but a route with no session in its path can never answer
# it: analysing a paper creates the session, and listing sessions finds none "unknown". Keep /openapi.json (what generated
# clients are built from) to the responses the service can really send.
_NO_SESSION_ROUTES = (("/api/prerequisites/analyze", "post"), ("/api/session", "get"))


_default_openapi = app.openapi


def _openapi_schema():
    first_build = app.openapi_schema is None
    schema = _default_openapi()
    if first_build:  # FastAPI caches the schema it returns, so it is trimmed once
        for path, method in _NO_SESSION_ROUTES:
            schema["paths"][path][method]["responses"].pop("404", None)
    return schema


app.openapi = _openapi_schema
