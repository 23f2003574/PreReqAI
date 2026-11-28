"""End-to-end answer grounding on the 36 real-paper questions (retrieval_questions.json: AI-written, unreviewed, PROVISIONAL): each question goes through the tutor's real answer path, not just the search.

Per answer: it `contains_gold` (the gold phrase appears in the answer), it `abstained` (the tutor said it found no passage), it is `quoted_without_gold` (it quotes the paper but not the gold phrase: right
region at best), or `off_target` (it states built-in text with no quotation and no gold phrase). `citations_verified` is the share of quoted sentences that are an exact part of the text of the page they
cite. The search metric (retrieval_real.py) says whether the right sentence was FOUND; this one says whether the learner is SHOWN it."""
import dataclasses
import re

from . import retrieval_real

_QUOTE = re.compile(r"“([^”]+)”")


def _flat(text):
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def evaluate(papers, data=None):
    """{"questions", "contains_gold", "abstained", "quoted_without_gold", "off_target", "citations_verified", "citations", "status"}; `papers`: {paper id: session id of an analysed paper}."""
    from backend.platform import platform
    from backend.session import TutorMode, session_manager

    data = data or retrieval_real.load()
    counts = {"contains_gold": 0, "abstained": 0, "quoted_without_gold": 0, "off_target": 0}
    quotes = verified = total = 0
    for question in data["questions"]:
        if question["paper"] not in papers:
            continue
        total += 1
        session = session_manager.get(papers[question["paper"]])
        result = platform.learning.answer(session=session, paper=session.paper, question=question["question"], mode=TutorMode.INTUITION, topic=None)
        text = " ".join(dataclasses.asdict(r)["answer"] for r in result.get("responses") or [])
        pages = {page.page_number: _flat(page.text) for page in getattr(session.paper, "pages", []) or []}
        everything = " ".join(pages.values())
        for quote in _QUOTE.findall(text):
            quotes += 1
            verified += _flat(quote) in everything
        if _flat(question["gold"]) in _flat(text):
            counts["contains_gold"] += 1
        elif "could not find a passage" in text:
            counts["abstained"] += 1
        elif _QUOTE.search(text):
            counts["quoted_without_gold"] += 1
        else:
            counts["off_target"] += 1
    return {"questions": total, **counts, "citations": quotes, "citations_verified": (verified / quotes if quotes else 1.0), "status": data["status"]}
