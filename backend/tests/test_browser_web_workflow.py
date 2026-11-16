"""Browser-level verification of the web page: the real app is served by uvicorn and driven in Chromium through user interactions.

Run: `pip install -r requirements-browser.txt && python -m playwright install chromium && python -m pytest -m browser backend/tests/test_browser_web_workflow.py`
(PREREQAI_CHROMIUM=/path/to/chromium uses an existing browser instead). Without Playwright or a browser the tests are skipped, so the backend suite is
unaffected. Nothing leaves the machine: the built-in tutor and a generated sample paper are used, no LLM and no network."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError, sync_playwright  # noqa: E402

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "prerequisites" / "sample-paper.pdf"


def _launch(directory, **extra):
    """(process, url) of a real server using `directory` for its sessions; no profile, tutor provider, key or network."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "PREREQAI_SESSION_DIR": str(directory), "PYTHONPATH": str(ROOT), **extra}
    for name in ("PREREQAI_PROFILE_DIR", "PREREQAI_TUTOR_PROVIDER", "GEMINI_API_KEY", "PREREQAI_MAX_ANALYSIS_SECONDS"):
        if name not in extra:
            env.pop(name, None)
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            return process, url
        except OSError:
            time.sleep(0.5)
    process.kill()
    pytest.fail("the PreReqAI server did not start")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    process, url = _launch(tmp_path_factory.mktemp("sessions"))
    yield url
    process.terminate()
    process.wait(timeout=10)


@pytest.fixture
def lone_server(tmp_path):
    """A server of its own (empty history, a profile directory) for the tests that count saved analyses."""
    process, url = _launch(tmp_path / "sessions", PREREQAI_PROFILE_DIR=str(tmp_path / "profiles"))
    yield url, tmp_path
    process.terminate()
    process.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        path = os.environ.get("PREREQAI_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None)
        try:
            instance = playwright.chromium.launch(args=["--no-sandbox"], **({"executable_path": path} if path else {}))
        except PlaywrightError as error:
            pytest.skip(f"no Chromium available ({str(error).splitlines()[0]}); run `python -m playwright install chromium`")
        yield instance
        instance.close()


@pytest.fixture
def page(browser, server):
    context = browser.new_context(viewport={"width": 1100, "height": 1600})
    page = context.new_page()
    page.set_default_timeout(15000)
    page.goto(server)
    yield page
    context.close()


def analyse(page, path=SAMPLE, known=""):
    page.set_input_files("#paper", str(path))
    if known:
        page.fill("#known", known)
    page.click("#submit")
    page.wait_for_selector("#results:not([hidden])")


def test_the_served_application_loads_with_an_empty_form(page):
    assert page.title() and page.locator("#form").is_visible() and page.locator("#results").is_hidden()
    assert page.locator("#submit").inner_text() == "Analyse paper" and page.locator("#status").inner_text() == ""


def test_uploading_a_pdf_shows_the_analysis_recommendations_plan_and_schedule(page):
    count = lambda: len(page.evaluate("fetch('/api/session').then(r => r.json())")["sessions"])
    before = count()
    analyse(page)
    assert "Attention Is All You Need" in page.locator("#meta").inner_text()
    concepts = page.locator("#concepts").inner_text()
    assert all(name in concepts for name in ("Transformer", "Softmax", "Gradient Descent"))
    gaps = page.locator("#gaps table tr")
    assert gaps.count() > 3 and "Linear Algebra" in page.locator("#gaps").inner_text() and "Evidence in the paper" in page.locator("#gaps").inner_text()
    assert page.locator("#plan table tr").count() > 3 and page.locator("#schedule table tr").count() > 1
    assert "Linear Algebra" in page.locator("#paths").inner_text()
    assert count() == before + 1  # the page created exactly one server session


def test_progress_updates_change_the_page_and_the_server(page, server):
    analyse(page)
    rows_before = page.locator("#plan table tr").count()
    first = page.locator("#plan table tr").nth(1)
    concept = first.locator("td").nth(2).inner_text()
    first.locator("input[type=checkbox]").check()
    page.wait_for_function("document.querySelector('#plan input:checked') !== null && !document.querySelector('#plan input:disabled')")
    sid = page.evaluate("localStorage.getItem('prereqai.session')")
    body = page.evaluate("(sid) => fetch('/api/session/' + sid).then(r => r.json())", sid)
    assert {p["concept"]: p["completed"] for p in body["study_progress"]}[concept] is True
    page.locator("#plan table tr").nth(2).get_by_role("button", name="I already know this").click()
    page.wait_for_function("(n) => document.querySelectorAll('#plan table tr').length < n", arg=rows_before)
    assert page.locator(".known-list").inner_text().startswith("Marked as known")


def test_a_tutor_question_is_answered_in_the_page_and_unanswerable_ones_are_declined(page):
    analyse(page)
    page.fill("#question", "What is attention?")
    page.click("#askBtn")
    page.wait_for_function("document.querySelector('#answers').innerText.includes('Attention:')")
    assert "No tutoring model is configured" in page.locator("#answers").inner_text()  # the built-in tutor, disclosed on the page
    page.fill("#question", "What does it say about quantum gravity?")
    page.click("#askBtn")
    page.wait_for_function("document.querySelector('#answers').innerText.includes('I could not find a passage')")
    page.fill("#question", "")
    page.click("#askBtn")
    assert "Type a question first" in page.locator("#askMsg").inner_text()


def test_a_quiz_round_runs_to_completion_and_updates_mastery(page):
    analyse(page)
    page.select_option("#quizConcept", "Transformer")
    for _ in range(3):  # Transformer has three questions: one round
        page.click("#quizNext")
        page.get_by_role("button", name="Show answer").click()
        page.get_by_role("button", name="I knew it").click()
        page.wait_for_function("document.querySelector('#quizMsg').innerText.includes('Recorded')")
    page.wait_for_function("document.querySelector('#quizRound').innerText.includes('Round complete on Transformer: you knew 3 of 3')")
    assert "Transformer" in page.locator("#mastery").inner_text() and "mastered" in page.locator("#mastery").inner_text()


def test_the_session_is_restored_after_a_reload_and_a_vanished_session_is_handled(page, server):
    analyse(page)
    page.reload()
    page.wait_for_selector("#results:not([hidden])")
    assert "Attention Is All You Need" in page.locator("#meta").inner_text() and page.locator("#plan table tr").count() > 3
    sid = page.evaluate("localStorage.getItem('prereqai.session')")
    page.evaluate("(sid) => fetch('/api/session/' + sid, {method: 'DELETE'})", sid)
    page.reload()
    page.wait_for_function("document.querySelector('#form') !== null")
    assert page.locator("#results").is_hidden() and page.locator("#form").is_visible()


def test_invalid_input_and_failed_requests_show_clear_errors(page, tmp_path):
    page.click("#submit")  # nothing chosen
    assert page.locator("#status .msg.error").count() == 1
    bad = tmp_path / "not-a-paper.pdf"
    bad.write_bytes(b"this is not a pdf")
    page.set_input_files("#paper", str(bad))
    page.click("#submit")
    page.wait_for_selector("#status .msg.error")
    assert page.locator("#results").is_hidden() and page.locator("#status .msg.error").inner_text().strip()
    page.fill("#hours", "99")
    page.set_input_files("#paper", str(SAMPLE))
    page.click("#submit")
    assert "at most 24" in page.locator("#status").inner_text()
    page.fill("#hours", "")
    page.route("**/api/prerequisites/analyze", lambda route: route.abort())
    page.click("#submit")
    page.wait_for_function("document.querySelector('#status').innerText.includes('Could not reach the PreReqAI server')")
    page.unroute("**/api/prerequisites/analyze")
    page.route("**/api/prerequisites/analyze", lambda route: route.fulfill(status=500, content_type="application/json", body="{}"))
    page.click("#submit")
    page.wait_for_selector("#status .msg.error")
    assert page.locator("#results").is_hidden()


def test_failed_tutor_and_quiz_requests_and_unsupported_topics_are_reported(page):
    analyse(page)
    page.route("**/question", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail": "boom"}'))
    page.fill("#question", "What is attention?")
    page.click("#askBtn")
    page.wait_for_selector("#askMsg .msg.error")
    page.unroute("**/question")
    page.route("**/quiz/question*", lambda route: route.fulfill(status=422, content_type="application/json", body='{"status": "failure", "detail": "No questions for that topic"}'))
    page.click("#quizNext")
    page.wait_for_selector("#quizMsg .msg.error")
    assert page.locator("#quizCard .card").count() == 0


def test_history_lists_analyses_resumes_one_and_deletes_only_after_confirmation(browser, lone_server):
    url, tmp_path = lone_server
    context = browser.new_context(viewport={"width": 1100, "height": 1800})
    page = context.new_page()
    page.set_default_timeout(15000)
    page.goto(url)
    assert page.locator("#history").is_hidden()  # nothing analysed yet
    page.fill("#profile", "me")
    analyse(page, known="Linear Algebra")  # a profile file now exists, apart from the analyses
    first = page.evaluate("localStorage.getItem('prereqai.session')")
    page.locator("#plan table tr").nth(1).locator("input[type=checkbox]").check()
    page.wait_for_function("document.querySelector('#plan input:checked') !== null")
    page.reload()
    page.fill("#profile", "")
    analyse(page)  # a second, separate analysis: it must not replace the first
    second = page.evaluate("localStorage.getItem('prereqai.session')")
    assert second != first
    page.wait_for_function("document.querySelectorAll('#historyList .card').length === 2")
    cards = page.locator("#historyList .card")
    assert "(open now)" in cards.nth(0).inner_text() and "1 of" in cards.nth(1).inner_text() and "Attention Is All You Need" in cards.nth(1).inner_text()
    cards.nth(1).get_by_role("button", name="Resume").click()  # resuming is a different action from the new-analysis form
    page.wait_for_function("document.querySelector('#status').innerText.includes('Restored your saved session')")
    assert page.evaluate("localStorage.getItem('prereqai.session')") == first and page.locator("#plan input:checked").count() == 1
    assert page.locator("#newHeading").inner_text() == "Start a new analysis"
    cards = page.locator("#historyList .card")
    cards.nth(0).get_by_role("button", name="Delete").click()  # asks first; nothing is removed yet
    page.wait_for_function("document.querySelector('#historyList').innerText.includes('Delete this analysis for good?')")
    assert page.locator("#historyList .card").count() == 2 and len(page.evaluate("fetch('/api/session').then(r => r.json())")["sessions"]) == 2
    page.get_by_role("button", name="Keep it").click()
    page.wait_for_function("!document.querySelector('#historyList').innerText.includes('Delete this analysis for good?')")
    page.locator("#historyList .card").nth(0).get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Yes, delete it").click()
    page.wait_for_function("document.querySelectorAll('#historyList .card').length === 1")
    assert [s["session_id"] for s in page.evaluate("fetch('/api/session').then(r => r.json())")["sessions"]] == [first]
    assert (tmp_path / "profiles" / "me.json").is_file()  # learner profiles are independent of deleting an analysis
    context.close()


def test_a_damaged_saved_analysis_is_shown_and_can_be_removed_without_breaking_the_page(browser, lone_server):
    url, tmp_path = lone_server
    (tmp_path / "sessions").mkdir(exist_ok=True)
    (tmp_path / "sessions" / "deadbeef-dead-beef-dead-beefdeadbeef.session").write_bytes(b"garbage")
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(15000)
    page.goto(url)
    page.wait_for_selector("#historyList .msg.warn")
    assert "cannot be read" in page.locator("#historyList").inner_text() and page.locator("#form").is_visible()
    page.get_by_role("button", name="Remove it").click()
    page.wait_for_function("document.querySelector('#history').hidden")
    assert not (tmp_path / "sessions" / "deadbeef-dead-beef-dead-beefdeadbeef.session").exists()
    page.route("**/api/session", lambda route: route.fulfill(status=500, content_type="application/json", body="{}"))
    page.reload()
    page.wait_for_function("document.querySelector('#historyList').innerText.includes('could not be listed')")
    assert page.locator("#form").is_visible()
    context.close()
