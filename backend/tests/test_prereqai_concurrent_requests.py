"""A slow analysis must not freeze the server: while one upload is being analysed, other requests are
still answered. (The analysis is blocking, CPU-bound work, so the route has to run it off the event loop.)"""
import asyncio
import time
from pathlib import Path

import httpx2 as httpx  # the HTTP client requirements.txt provides (what starlette.testclient uses)

from backend.main import app
from backend.main import platform as main_platform

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
ANALYSIS_SECONDS = 0.6


def test_other_requests_are_served_while_an_analysis_is_running(monkeypatch):
    real_analyze = main_platform.analyze

    def slow_analyze(*args, **kwargs):
        time.sleep(ANALYSIS_SECONDS)  # stands in for a long, blocking analysis
        return real_analyze(*args, **kwargs)

    monkeypatch.setattr(main_platform, "analyze", slow_analyze)

    async def scenario():
        gaps = []

        async def watch_loop():  # a server that is serving other requests keeps ticking
            last = time.perf_counter()
            while True:
                await asyncio.sleep(0.01)
                now = time.perf_counter()
                gaps.append(now - last)
                last = now

        watcher = asyncio.create_task(watch_loop())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uploaded = await client.post(
                "/api/prerequisites/analyze", files={"paper": ("paper.pdf", SAMPLE.read_bytes(), "application/pdf")})
            missing = await client.get("/api/session/does-not-exist")
        watcher.cancel()
        return missing.status_code, max(gaps), uploaded

    status, longest_stall, uploaded = asyncio.run(scenario())

    assert status == 404
    assert longest_stall < ANALYSIS_SECONDS / 2, f"the event loop was blocked for {longest_stall:.2f}s by the analysis"
    assert uploaded.status_code == 200 and uploaded.json()["status"] == "success"
