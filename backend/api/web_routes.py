"""The browser interface: one static page that calls the existing /api/prerequisites/analyze endpoint."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

PAGE = Path(__file__).resolve().parents[1] / "web" / "index.html"


@router.get("/", include_in_schema=False)
def web_interface(request: Request):
    """The page, with the response's Content-Security-Policy nonce on its one script (only that script may run)."""
    nonce = getattr(request.state, "csp_nonce", "")
    html = PAGE.read_text(encoding="utf-8").replace("<script>", f'<script nonce="{nonce}">')
    return HTMLResponse(html)
