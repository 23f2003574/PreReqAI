"""Real-browser tests of the evidence, quiz explanation, review queue, calendar, reading list, curriculum, profile and cited-answer workflows: the page is driven by clicks and typing
against a real server (a stand-in for Google's package answers the Gemini tutor; nothing else is faked, and nothing leaves the machine except that no request to arXiv is allowed to run)."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from backend.tests.test_browser_web_workflow import ROOT, SAMPLE, _launch, analyse, browser  # noqa: E402,F401  (the shared server launcher and Chromium fixture)

pytestmark = pytest.mark.browser
DPO = ROOT / "backend" / "prereqai_eval" / "benchmark" / "pdfs" / "dpo.pdf"
MIXTRAL = ROOT / "backend" / "prereqai_eval" / "benchmark" / "pdfs" / "mixtral.pdf"
STUB = Path(__file__).resolve().parent / "browser_support"


@pytest.fixture
def rich(tmp_path):
    """A server with a profile directory and the stand-in Gemini package enabled (a key is required to enable it, a dummy one)."""
    process, url = _launch(tmp_path / "sessions", PREREQAI_PROFILE_DIR=str(tmp_path / "profiles"), PREREQAI_TUTOR_PROVIDER="gemini", GEMINI_API_KEY="stand-in",
                           PYTHONPATH=f"{STUB}{os.pathsep}{ROOT}")
    yield url, tmp_path
    process.terminate()
    process.wait(timeout=10)


@pytest.fixture
def plain(tmp_path):
    process, url = _launch(tmp_path / "sessions")
    yield url
    process.terminate()
    process.wait(timeout=10)


def open_page(browser, url, timeout=60000):
    context = browser.new_context(viewport={"width": 1100, "height": 1800}, bypass_csp=True)  # Playwright waits evaluate strings; the page is served with a strict CSP
    page = context.new_page()
    page.set_default_timeout(timeout)
    page.goto(url)
    return context, page


def test_evidence_is_shown_with_page_section_and_passage_id_and_can_be_opened(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page)
    summary = page.locator("#concepts details summary").first
    assert "passage" in summary.inner_text()
    summary.click()
    quote = page.locator("#concepts details[open] blockquote").first
    assert quote.is_visible() and len(quote.inner_text()) > 20 and quote.inner_text().startswith("“")
    assert re.search(r"Page \d+, section .+ \[p-[0-9a-f]{10}\]", page.locator("#concepts details[open] p.meta").first.inner_text())
    context.close()


def test_the_quiz_explanation_appears_only_after_the_answer_is_revealed(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page, DPO)
    page.select_option("#quizConcept", "Reward Model")
    page.click("#quizNext")
    page.wait_for_selector("#quizCard button:has-text('Show answer')")
    assert page.locator("#quizExplanation").count() == 0
    page.click("#quizCard button:has-text('Show answer')")
    page.wait_for_selector("#quizExplanation")
    assert page.locator("#quizExplanation").inner_text().startswith("Why: ") and "Answer: " in page.locator("#quizCard").inner_text()
    context.close()


def test_the_review_queue_lists_due_questions_and_practising_one_opens_its_question(browser, rich):
    from backend import learner_profile, spaced_review

    url, tmp = rich
    context, page = open_page(browser, url)
    analyse(page)
    learner_profile.record_quiz(tmp / "profiles" / "default.json", "Softmax:1", "Softmax", "missed", spaced_review.now() - timedelta(days=2))
    page.click("#reviewBtn")
    page.wait_for_selector("#reviewList button:has-text('Practise Softmax')")
    assert "Softmax:1" in page.locator("#reviewList").inner_text() and "overdue" in page.locator("#reviewList").inner_text()
    page.click("#reviewList button:has-text('Practise Softmax')")
    page.wait_for_selector("#quizCard .card")
    assert page.locator("#quizCard").inner_text().startswith("Softmax")
    context.close()


def test_the_review_queue_says_so_when_nothing_is_due_or_profiles_are_off(browser, rich, plain):
    context, page = open_page(browser, rich[0])
    analyse(page)
    page.click("#reviewBtn")
    page.wait_for_selector("#reviewList p")
    assert "Nothing is due" in page.locator("#reviewList").inner_text()
    context.close()
    context, page = open_page(browser, plain)
    analyse(page)
    page.click("#reviewBtn")
    page.wait_for_selector("#reviewMsg .error, #reviewMsg [class*=error]")
    assert "profile" in page.locator("#reviewMsg").inner_text().lower()
    context.close()


def test_the_calendar_shows_feasibility_dates_a_download_link_and_missed_work(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page)
    page.click("#calendarBtn")
    page.wait_for_selector("#calendarBox table")
    assert page.locator("#calendarBox table tr").count() >= 2 and "No deadline" in page.locator("#calendarMsg").inner_text()
    page.fill("#deadline", (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d"))
    page.click("#calendarBtn")
    page.wait_for_function("document.querySelector('#calendarMsg').innerText.includes('study days')")
    assert "more a day" in page.locator("#calendarMsg").inner_text()  # a deadline too close to finish: the extra daily hours are named
    assert page.locator("#icsLink").is_visible() and "calendar.ics" in page.get_attribute("#icsLink", "href")
    sid = page.evaluate("localStorage.getItem(Object.keys(localStorage)[0])")
    long_ago = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    assert page.evaluate("async ([sid, d]) => (await fetch('/api/session/' + sid + '/plan-start?date=' + d, {method: 'POST'})).status", [sid, long_ago]) == 200
    page.reload()
    page.wait_for_selector("#results:not([hidden])")
    page.click("#calendarBtn")
    page.wait_for_selector("#missedBox p.warn")
    assert "nothing is lost" in page.locator("#missedBox").inner_text() and "planned for" in page.locator("#missedBox").inner_text()
    page.click("#restartPlan")
    page.wait_for_function("document.querySelector('#missedBox').innerText.trim() === ''")
    context.close()


def test_the_reading_list_is_fetched_on_a_click_and_a_work_is_analysed_only_when_chosen(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page, MIXTRAL)
    analysis_requests = []  # from here on, a request to analyse a paper is caught: the test never downloads one
    page.route("**/api/prerequisites/analyze", lambda route: (analysis_requests.append(route.request.post_data or ""), route.fulfill(status=422, content_type="application/json",
               body=json.dumps({"status": "failure", "stage": "x", "detail": "blocked by the test", "hint": "no download in tests"}))))

    page.click("#readingBtn")
    page.wait_for_selector("#readingList .card")
    assert page.locator("#readingList .card").count() >= 5 and analysis_requests == []  # listing downloads and analyses nothing
    page.locator("#readingList .card button:has-text('Analyse this next')").first.click()
    page.wait_for_timeout(500)
    assert len(analysis_requests) == 1 and re.search(r'name="source"\r\n\r\n(arXiv:|10\.)', analysis_requests[0])  # one explicit request, carrying the chosen work
    context.close()


def test_a_curriculum_is_planned_from_ticked_analyses_and_one_tick_is_an_error(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page)
    analyse(page, DPO)
    page.reload()
    page.wait_for_selector("#historyList .card")
    page.click("#curriculumBtn")
    assert "at least two" in page.locator("#curriculumMsg").inner_text()
    page.locator("#historyList input.pick").nth(0).check()
    page.click("#curriculumBtn")
    assert "at least two" in page.locator("#curriculumMsg").inner_text()
    page.locator("#historyList input.pick").nth(1).check()
    page.click("#curriculumBtn")
    page.wait_for_selector("#curriculumBox .card")
    text = page.locator("#curriculumBox").inner_text()
    assert text.startswith("Together:") and "1. " in text and "2. " in text and page.locator("#curriculumBox table").count() == 1
    context.close()


def test_the_profile_can_be_shown_edited_forgotten_and_exported(browser, rich):
    url, tmp = rich
    context, page = open_page(browser, url)
    page.fill("#profile", "me")
    analyse(page)
    page.fill("#profile", "ghost")
    page.click("#profileBtn")
    page.wait_for_selector("#profileMsg .error, #profileMsg [class*=error]")  # no profile of that name exists
    page.fill("#profile", "me")
    page.click("#profileBtn")
    page.wait_for_selector("#profileBody h3")
    page.fill("#profileConcept", "linear algebra")
    page.click("#profileKnown")
    page.wait_for_selector("#profileBody button[aria-label='Forget Linear Algebra']")
    assert "Known (1)" in page.locator("#profileBody").inner_text() and json.loads((tmp / "profiles" / "me.json").read_text())["known"] == ["Linear Algebra"]
    assert page.locator("#profileExport").is_visible() and page.get_attribute("#profileExport", "href").endswith("/api/profiles/me/export")
    page.click("#profileBody button[aria-label='Forget Linear Algebra']")
    page.wait_for_function("document.querySelector('#profileBody').innerText.includes('Known (0)')")
    assert json.loads((tmp / "profiles" / "me.json").read_text())["known"] == []
    page.fill("#profileConcept", "Astrology")
    page.click("#profileKnown")
    page.wait_for_selector("#profileMsg .error, #profileMsg [class*=error]")
    assert "Astrology" in page.locator("#profileMsg").inner_text()  # an invalid name is refused with its reason
    context.close()


def test_a_cited_tutor_answer_shows_its_verified_quotation(browser, rich):
    url, _ = rich
    context, page = open_page(browser, url)
    analyse(page)
    page.fill("#question", "What is attention?")
    page.click("#askBtn")
    page.wait_for_selector("#answers .card blockquote")
    card = page.locator("#answers .card").first
    assert "Checked against the paper" in card.inner_text() and "(page" in card.locator("blockquote").first.inner_text() and "generated by" in card.inner_text()
    context.close()


def test_the_prerequisite_tree_opens_and_closes_and_names_every_level(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page)
    assert page.locator("#tree details.node").count() >= 1
    page.click("#treeOpen")
    assert page.locator("#tree details.node:not([open])").count() == 0
    assert "Transformer" in page.locator("#tree").inner_text() and "Linear Algebra" in page.locator("#tree").inner_text()  # a prerequisite of a prerequisite
    page.click("#treeClose")
    assert page.locator("#tree details.node[open]").count() == 0
    first = page.locator("#tree details.node > summary").first
    first.click()  # one branch opens on its own, by keyboard-reachable summary
    assert page.locator("#tree details.node[open]").count() >= 1
    context.close()


def test_mathematics_difficulty_roadmap_and_actions_panels_show_the_report(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page)
    math = page.locator("#math").inner_text()
    assert "Extraction confidence:" in page.locator("#confidence").inner_text()  # the learner is told how far to trust the extraction
    assert "Linear Algebra" in math and "Calculus" in math and "No display equations were found" in math and "No specific mathematical notation PreReqAI knows was recognised" in math  # the sample paper has no equations: said, not blank
    assert page.locator("#why").inner_text().startswith("Advanced") and "Missing Prerequisites" in page.locator("#why").inner_text()
    roadmap = page.locator("#roadmap").inner_text()
    assert "Roadmap (in study order)" in roadmap and "MIT 18.06 Linear Algebra" in roadmap and "Next actions" in roadmap and "Study Linear Algebra" in roadmap
    context.close()


def test_a_real_papers_equations_and_empty_states_are_readable(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page, DPO)
    math = page.locator("#math").inner_text()
    assert re.search(r"Equation \(7\), page 4, section 4 Direct Preference Optimization", math) and "LDPO" in math
    assert "Specific skills your equations need" in math and "Expectation of a random variable" in math and "Eq. (7), p. 4" in math  # the skills, each with its equation
    context.close()


def test_the_new_panels_survive_a_study_action_and_never_run_injected_markup(browser, plain):
    context, page = open_page(browser, plain)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    analyse(page)
    page.locator("#plan input[type=checkbox]").first.check()
    page.wait_for_function("document.querySelectorAll('#tree .badge.studied').length >= 1")
    assert not errors and page.locator("#tree script, #math script, #roadmap script").count() == 0
    context.close()


def test_paper_questions_are_answered_checked_against_the_paper_and_recorded(browser, plain):
    context, page = open_page(browser, plain)
    analyse(page, DPO)
    page.click("#pqNext")
    page.wait_for_selector("#pqPrompt")
    prompt = page.locator("#pqPrompt").inner_text()
    assert "_____" in prompt and page.locator("#pqAnswer").count() == 0  # the answer is not on the page before it is asked for
    page.fill("#pqAttempt", "zebra")
    page.click("#pqCard button:has-text('Check and show the answer')")
    page.wait_for_selector("#pqAnswer")
    assert page.locator("#pqCard blockquote").inner_text().startswith("“") and re.search(r"Page \d+, section ", page.locator("#pqCard").inner_text())
    assert "Your answer was: zebra" in page.locator("#pqCard").inner_text()
    assert "Assessed: not correct" in page.locator("#pqCard").inner_text()  # the server graded the wrong answer before showing the quotation
    page.wait_for_function("document.querySelector('#pqMsg').innerText.indexOf('Assessed') >= 0")
    assert page.locator("#mastery").inner_text().strip() != ""
    page.click("#pqNext")
    page.wait_for_function("(old) => { var e = document.querySelector('#pqPrompt'); return e && e.innerText !== old; }", arg=prompt)  # the answered card stays on screen until the next one arrives
    assert page.locator("#pqPrompt").inner_text() != prompt  # the next question is a different one
    context.close()


def test_the_profile_table_shows_the_estimate_its_range_the_refresh_state_and_survives_old_entries(browser, rich):
    from backend import learner_profile, spaced_review
    url, tmp = rich
    now = spaced_review.now()

    def entry(concept, days_ago, graded=True):
        seen = spaced_review.stamp(now - timedelta(days=days_ago))
        return {"concept": concept, "attempts": 2, "knew": 2, "missed": 0, "streak": 2, "last_outcome": "knew", "first_seen": "2026-10-01T00:00:00Z", "last_seen": seen, "interval_hours": 72.0, "due": seen,
                **({"graded_attempts": 2, "graded_correct": 2, "graded_streak": 2} if graded else {})}
    quiz = {"Calculus:1": entry("Calculus", 1), "Calculus:2": entry("Calculus", 1), "Probability:1": entry("Probability", 40), "Probability:2": entry("Probability", 40), "Softmax:1": entry("Softmax", 3, graded=False)}
    learner_profile.save(tmp / "profiles" / "me.json", [], [], quiz)
    context, page = open_page(browser, url)
    page.fill("#profile", "me")
    analyse(page)
    page.fill("#profile", "me")
    page.click("#profileBtn")
    page.wait_for_selector("#profileBody table")
    rows = {row.locator("td").first.inner_text(): row.inner_text() for row in page.locator("#profileBody table tr").all() if row.locator("td").count()}
    assert "mastered" in rows["Calculus"] and re.search(r"\d+% \(range \d+-\d+%\)", rows["Calculus"]) and "1 day(s) ago" in rows["Calculus"]
    assert "Needs refresh" in rows["Probability"] and "40 days ago" in rows["Probability"] and "answer a few questions again" in rows["Probability"] and "at your last graded answer" in rows["Probability"]
    assert "no graded answers yet" in rows["Softmax"] and "range" not in rows["Softmax"]
    assert "not a calibrated probability" in page.locator("#profileBody").inner_text()
    context.close()


def test_the_page_asks_for_the_access_token_once_and_then_works_with_it(browser, tmp_path):
    process, url = _launch(tmp_path / "sessions", PREREQAI_API_TOKEN="browser-token-1")
    try:
        context, page = open_page(browser, url)
        prompts = []

        def answer(dialog):
            prompts.append(dialog.message)
            dialog.accept("browser-token-1")
        page.on("dialog", answer)
        analyse(page)  # every /api/ call fails once with 401, the page asks, then retries with the token
        assert len(prompts) == 1 and "PREREQAI_API_TOKEN" in prompts[0]
        assert page.evaluate("sessionStorage.getItem('prereqaiToken')") == "browser-token-1"
        assert page.locator("#concepts").inner_text().strip()
        context.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
