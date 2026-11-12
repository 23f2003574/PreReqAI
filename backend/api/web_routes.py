"""The browser interface: one static page that calls the existing /api/prerequisites/analyze endpoint."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

PAGE = Path(__file__).resolve().parents[1] / "web" / "index.html"


@router.get("/", include_in_schema=False)
def web_interface():
    return FileResponse(PAGE, media_type="text/html; charset=utf-8")
