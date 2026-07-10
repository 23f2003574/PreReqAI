from fastapi import FastAPI

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
)

from backend.platform import (
    PreReqAIPlatform,
)

app = FastAPI(
    title="PreReqAI",
)

platform = (
    PreReqAIPlatform()
)

app.include_router(
    prerequisite_router,
)

app.include_router(
    session_router,
)
