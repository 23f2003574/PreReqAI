from fastapi import FastAPI

from backend.api.prerequisite_routes import (
    router as prerequisite_router,
)

from backend.api.session_routes import (
    router as session_router,
)

from backend.engine import (
    InteractiveResearchEngine,
)

app = FastAPI(
    title="PreReqAI",
)

interactive_engine = (
    InteractiveResearchEngine()
)

app.include_router(
    prerequisite_router,
)

app.include_router(
    session_router,
)
