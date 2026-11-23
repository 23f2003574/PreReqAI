"""BM25 builds its per-paper statistics once and reuses them: results are identical to rebuilding for every question, the index follows the paper it belongs to, and a search of a large paper is much faster."""
import gc
import math
import time
from types import SimpleNamespace

import pytest

from backend import retrieval
from backend.evidence import passage_id, quotable_sentences
from backend.models import Paper, PaperSection, Paragraph
from backend.prerequisites.missing_prerequisite_analyzer import section_role
from backend.tests.test_prereqai_retrieval import sentence

pytestmark = pytest.mark.prereqai
RARE = "The chunking scheme splits a long sequence into overlapping windows before encoding."


def paper_of(count, rare=True):
    paper = Paper(source_path="s.pdf", metadata=None)
    paper.paragraphs, pages = [], {}
    for p in range(1, count + 1):
        text = " ".join(sentence(p * 3 + k) for k in range(3)) + (" " + RARE if rare and p == 5 else "")
        paper.paragraphs.append(Paragraph(p, ("1 Introduction", "2 Related Work", "3 Method", "4 Experiments")[p % 4], text, p))
        pages[p] = text
    paper.pages = [SimpleNamespace(page_number=n, text=t) for n, t in pages.items()]
    paper.sections, paper.concepts = [PaperSection(title="3 Method", content="x")], []
    return paper


def rebuilt_every_time(paper, question, limit=5):
    """The search as it was before the index existed: every statistic recomputed for each question (kept here as the reference the optimised search must equal)."""
    candidates, query = quotable_sentences(paper), retrieval._query(paper, question)
    if not query or not candidates:
        return []
    docs = [retrieval._tokens(s) for _, _, _, _, s, _ in candidates]
    total, average = len(docs), (sum(len(d) for d in docs) / len(docs)) or 1.0
    frequency = {term: sum(term in set(doc) for doc in docs) for term in query}
    scored = []
    for index, (doc, (_, _, _, section, sentence_, number)) in enumerate(zip(docs, candidates)):
        matched = [term for term in query if term in set(doc)]
        if not matched or (len(matched) < retrieval.MIN_TERMS and len(query) >= retrieval.MIN_TERMS and not (len(matched[0]) >= retrieval.RARE_MIN_CHARS and frequency[matched[0]] <= retrieval.RARE_SHARE * total)):
            continue
        score = 0.0
        for term in matched:
            idf = math.log(1 + (total - frequency[term] + 0.5) / (frequency[term] + 0.5))
            count = doc.count(term)
            score += idf * count * (retrieval.K1 + 1) / (count + retrieval.K1 * (1 - retrieval.B + retrieval.B * len(doc) / average))
        scored.append((-(score * retrieval.ROLE_WEIGHT[section_role(section)]), index, section, sentence_, number))
    if not scored:
        return []
    scored.sort(key=lambda item: item[:2])
    best = -scored[0][0]
    return [{"passage_id": passage_id(section, s), "sentence": s, "page_number": number, "section": section, "concepts": []} for score, _, section, s, number in scored[:limit] if -score >= retrieval.MIN_RELATIVE * best]


QUESTIONS = ["What happened with the stellar spectra and the seismic tomography?", "How does chunking work in practice nowadays?", "Which tidal turbines were compared against glacial moraines?",
             "What about coral bleaching and bacterial plasmids?", "Explain softmax on kelp forests.", "What about zzzz qqqq?", ""]


@pytest.mark.parametrize("question", QUESTIONS)
def test_the_indexed_search_returns_exactly_what_rebuilding_everything_returns(question):
    paper = paper_of(60)
    for _ in range(2):  # the second call is served from the index
        assert retrieval.bm25_search(paper, question, 5) == rebuilt_every_time(paper, question, 5)


def test_the_index_is_built_once_per_paper_and_follows_changes_and_deletion(monkeypatch):
    calls = []
    real = retrieval._tokens
    monkeypatch.setattr(retrieval, "_tokens", lambda text: calls.append(1) or real(text))
    paper = paper_of(30)
    retrieval.bm25_search(paper, "How does chunking work in practice nowadays?", 5)
    built = len(calls)
    for _ in range(5):
        retrieval.bm25_search(paper, "What about stellar spectra today?", 5)
    assert built > 0 and len(calls) - built <= 5 * 6  # only the question's own words are tokenised again, never the sentences
    other = paper_of(30, rare=False)
    assert retrieval.bm25_search(other, "How does chunking work in practice nowadays?", 5) == []  # another paper has its own index
    paper.paragraphs = paper.paragraphs[:2]
    paper.pages = paper.pages[:2]
    assert retrieval.bm25_search(paper, "How does chunking work in practice nowadays?", 5) == []  # a changed paper is indexed again
    key = id(other)
    del other
    gc.collect()
    assert key not in retrieval._INDEXES


def test_a_search_of_a_large_paper_is_much_faster_once_indexed():
    paper = paper_of(500)
    question = "What happened with the stellar spectra and the seismic tomography?"
    cold = warm = float("inf")
    for _ in range(3):
        retrieval._INDEXES.clear()
        start = time.perf_counter()
        retrieval.bm25_search(paper, question, 5)
        cold = min(cold, time.perf_counter() - start)
    for _ in range(5):
        start = time.perf_counter()
        retrieval.bm25_search(paper, question, 5)
        warm = min(warm, time.perf_counter() - start)
    assert warm * 3 < cold, (cold, warm)  # about 1,500 sentences; measured at 10 to 15 times on this machine
