from fastapi import FastAPI

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
)

from backend.api.recovery_decision_routes import (
    router as recovery_decision_router,
)

from backend.platform import (  # noqa: F401  (kept as backend.main.platform)
    platform,
)

app = FastAPI(
    title="PreReqAI",
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
