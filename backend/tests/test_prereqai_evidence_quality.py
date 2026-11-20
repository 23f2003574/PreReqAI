"""Evidence passage quality: chart and table residue and trailing page numbers are kept out, useful sentences are ranked first, quotations stay exact, and the documented spot-check is reproducible."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.evidence import build_evidence, residue_share, usefulness
from backend.models import DetectedConcept, Paragraph
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
AXIS = "0.0\n2.5\n5.0\n7.5\n10.0\n12.5\n15.0\n17.5\n20.0\nKL(\nref)\n0.4\n0.5\n0.6\n0.7\n0.8\n0.9\n1.0\nReward\nIMDb Sentiment Generation\nDPO (Ours)\nUnlikelihood\nPPO (Our impl.)"


def fake(paragraphs, pages, concepts=("Softmax",)):
    return SimpleNamespace(paragraphs=paragraphs, pages=[SimpleNamespace(page_number=n, text=t) for n, t in pages], concepts=[DetectedConcept(name=c, domain="x", occurrences=1) for c in concepts])


def test_chart_axis_labels_and_numeric_tables_are_residue_and_prose_is_not():
    assert residue_share(AXIS) == 1.0 and residue_share("0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 12.5 softmax 3.3") > 0.5
    assert residue_share("The softmax function turns the scores of every token into a probability distribution over the sequence.") < 0.1
    assert residue_share("where x = (a + b) / 2 and p(y | x) is the softmax of the scores") < 0.35  # a sentence with a little mathematics is prose


def test_residue_is_never_selected_and_a_trailing_page_number_is_removed_without_changing_the_quotation():
    prose = "The softmax function turns the scores of every token into a probability distribution."
    page = f"{AXIS} softmax\n\n{prose}\n6"
    found = build_evidence(fake([Paragraph(1, "Method", f"{AXIS} softmax", 1), Paragraph(2, "Method", f"{prose}\n6", 1)], [(1, page)]))["Softmax"]
    assert [p["sentence"] for p in found] == [prose]  # the axis labels are gone and "\n6" is not part of the sentence
    assert found[0]["sentence"] in page and found[0]["page_number"] == 1


def test_a_sentence_that_genuinely_ends_in_a_number_keeps_it():
    sentence = "The model uses the softmax with a temperature of 0.7 and a top-k value of 40."
    found = build_evidence(fake([Paragraph(1, "Method", sentence, 1)], [(1, sentence)]))["Softmax"]
    assert found[0]["sentence"] == sentence


def test_definitions_and_methods_rank_above_incidental_mentions_and_appendices_below_the_body():
    incidental = "Results for the softmax baseline are listed in Table 3 for all seven datasets used here."
    defining = "The softmax is a function that turns a vector of scores into a probability distribution."
    paragraphs = [Paragraph(1, "6 Experiments", incidental, 1), Paragraph(2, "2 Method", defining, 1), Paragraph(3, "B Implementation Details", defining.replace("The", "Our"), 1)]
    found = build_evidence(fake(paragraphs, [(1, " ".join([incidental, defining, defining.replace("The", "Our")]))]))["Softmax"]
    assert found[0]["sentence"] == defining and found[0]["section"] == "2 Method"
    assert [p["section"] for p in found][-1] in ("6 Experiments", "B Implementation Details") and found == build_evidence(fake(paragraphs, [(1, " ".join([incidental, defining, defining.replace("The", "Our")]))]))["Softmax"]
    assert usefulness(defining, "2 Method", re.compile("softmax", re.I)) > usefulness(incidental, "6 Experiments", re.compile("softmax", re.I))


def test_the_number_of_passages_per_concept_stays_bounded():
    text = " ".join(f"The softmax of the scores in layer {i} is a probability distribution over the tokens." for i in range(12))
    assert len(build_evidence(fake([Paragraph(1, "Method", text, 1)], [(1, text)]))["Softmax"]) == 3


@pytest.fixture(scope="module")
def papers(tmp_path_factory):
    out = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PREREQAI_SESSION_DIR", str(tmp_path_factory.mktemp("sessions")))
        for pid in ("dpo", "mixtral", "chain-of-thought"):
            outcome = platform.analyze(f"backend/prereqai_eval/benchmark/pdfs/{pid}.pdf")
            out[pid] = (outcome["report"]["concept_evidence"], {p.page_number: p.text for p in session_manager.get(outcome["session_id"]).paper.pages})
        session_manager.sessions.clear()
    return out


def test_no_top_passage_on_the_three_real_papers_is_residue_and_every_one_is_an_exact_quotation(papers):
    checked = 0
    for pid, (evidence, pages) in papers.items():
        for item in evidence:
            for passage in item["passages"]:
                assert residue_share(passage["sentence"]) <= 0.35, (pid, item["concept"], passage["sentence"][:60])
                assert not re.search(r"\n\d{1,3}$", passage["sentence"]) and passage["sentence"] in pages[passage["page_number"]]
                checked += 1
    assert checked > 60


def test_the_documented_spot_check_matches_the_current_ranking_and_is_at_least_80_percent_useful(papers):
    doc = (Path(__file__).resolve().parents[2] / "docs" / "evidence-spot-check.md").read_text(encoding="utf-8")
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in doc.splitlines() if line.startswith("| ") and "`p-" in line]
    assert len(rows) >= 25 and len({row[1] for row in rows}) == 10
    for paper, concept, rank, passage_id, judgement, _ in rows:
        current = next(item for item in papers[paper][0] if item["concept"] == concept)["passages"]
        assert current[int(rank) - 1]["passage_id"] == passage_id.strip("`"), f"{paper}/{concept}: the ranking changed, redo the spot-check"
    assert sum(row[4] == "useful" for row in rows) / len(rows) >= 0.8
