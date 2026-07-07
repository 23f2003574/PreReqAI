from fastapi import FastAPI

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
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
