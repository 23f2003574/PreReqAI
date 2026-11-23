"""Quoted evidence is made of complete sentences: dotted abbreviations (w.r.t., U.S., Ph.D.) do not end one, and a fragment that starts mid-sentence or mid-word is not quoted as a sentence; checked on the six real papers."""
import re

import pytest

from backend.evidence import quotable_sentences
from backend.platform import platform
from backend.prereqai_eval import retrieval_real
from backend.sentences import is_continuation_fragment, split_sentences
from backend.session import session_manager

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("text,count", [
    ("The loss is lower w.r.t. Gaussian noise than w.r.t. Uniform noise.", 1),
    ("The U.S. Army funded the Ph.D. Thesis of J. R. R. Smith.", 1),
    ("We use a.k.a. Adam as the optimiser. It converges.", 2),
    ("Vaswani et al. (2017) introduced it, e.g. Figure 2. Following Eq. (3), we continue.", 2),
    ("It works. The next sentence is separate! Is it? Yes.", 4),
    ("We stop here, etc. The next one starts.", 2),  # "etc." stays a possible sentence end, as before
])
def test_dotted_abbreviations_do_not_end_a_sentence_and_real_boundaries_still_do(text, count):
    sentences = split_sentences(text)
    assert len(sentences) == count and " ".join(sentences) == text


@pytest.mark.parametrize("fragment", ["ing instability during fine-tuning, so we", "et al., 2022); GQA removes the waste.", "harmless [Askell et al., 2021]) with a smaller model.", "is harmful, unethical or racist.", "(and then it stops.", "“quoted words continue here"])
def test_a_fragment_that_starts_in_the_middle_is_recognised(fragment):
    assert is_continuation_fragment(fragment)


@pytest.mark.parametrize("sentence", ["The model is trained.", "where σ is the logistic function.", "Where β is a parameter.", "1st Critique: the response is harmful.", "(See Figure 2.)", "[12] showed it.", "“Quoted opening.” It goes on.", "3.5 times faster.", "ΔL is small."])
def test_complete_sentences_and_the_where_continuation_are_kept(sentence):
    assert not is_continuation_fragment(sentence)


@pytest.fixture(scope="module")
def papers():
    data = retrieval_real.load()
    paths = retrieval_real.pdf_paths(sorted({q["paper"] for q in data["questions"]}))
    return {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in paths.items()}


def test_no_real_paper_quotation_starts_mid_sentence_or_ends_at_a_listed_abbreviation(papers):
    total = 0
    for pid, paper in papers.items():
        for _, _, _, _, sentence, _ in quotable_sentences(paper):
            total += 1
            assert not is_continuation_fragment(sentence) or sentence.lstrip().lower().startswith("where "), (pid, sentence[:60])
            assert not re.search(r"(?<![A-Za-z])(?:et al|Eq|Eqs|Fig|Figs|w\.r\.t|i\.e|e\.g|cf|vs)\.$", sentence), (pid, sentence[-40:])
    assert total > 2300  # 2526 candidates before this change; the fragments (about 3%) are gone and nothing else is


def test_every_quotation_is_still_an_exact_part_of_its_page_and_retrieval_does_not_regress(papers):
    report = retrieval_real.evaluate(papers)["systems"]["hybrid"]
    assert report["quotations_verified"] == 1.0 and report["recall_at_k"] >= 0.75 and report["mrr"] >= 0.558  # the same numbers as before the change (0.750 and 0.559)
    for pid, paper in papers.items():
        pages = {page.page_number: page.text for page in paper.pages}
        assert all(sentence in pages[number] for _, _, _, _, sentence, number in quotable_sentences(paper) if number is not None), pid
