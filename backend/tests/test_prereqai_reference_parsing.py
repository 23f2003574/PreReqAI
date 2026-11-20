"""Reference parsing on real bibliographies: author initials, wrapped lines, author-year entries and citations, identifiers, and no invented metadata."""
from types import SimpleNamespace

import pytest

from backend.models import Paragraph, PaperReference
from backend.parsing.citation_extractor import CitationExtractor, author_year_index, author_year_numbers
from backend.parsing.reference_extractor import author_year_entries
from backend.parsing.reference_metadata_parser import ReferenceMetadataParser
from backend.platform import platform
from backend.reading_list import build_reading_list
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
parse = ReferenceMetadataParser().parse


def test_a_long_initial_style_author_list_with_a_wrapped_name_still_gives_the_title():
    entry = ("Y. Bai, A. Jones, K. Ndousse, Z. Hatfield- Dodds, D. Hernandez, T. Hume, P. F. Christiano, J. Leike, and R. Lowe. Training a helpful and harmless assistant with "
             "reinforcement learning from human feedback. arXiv preprint arXiv:2204.05862, 2022.")
    data = parse(entry)
    assert data["title"] == "Training a helpful and harmless assistant with reinforcement learning from human feedback"
    assert "Z. Hatfield-Dodds" in data["authors"] and "P. F. Christiano" in data["authors"] and data["year"] == 2022 and data["arxiv_id"] == "2204.05862" and data["doi"] is None


def test_two_authors_with_a_year_in_the_venue_do_not_swallow_the_title():
    data = parse("H. Bong and A. Rinaldo. Generalized results for the existence and consistency of the MLE in the Bradley-Terry-Luce model. International Conference on Machine Learning, "
                 "arXiv:2110.11487, 2022.")
    assert data["title"].startswith("Generalized results for the existence") and data["authors"] == ["H. Bong", "A. Rinaldo"] and data["venue"].startswith("International Conference")


def test_author_year_entries_give_authors_year_title_and_venue():
    data = parse("Aida Amini, Saadia Gabriel, Shanchuan Lin, and Hannaneh Hajishirzi. 2019. MathQA: Towards interpretable math word problem solving with operation-\nbased formalisms. "
                 "In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics.")
    assert data["authors"][0] == "Aida Amini" and data["year"] == 2019 and data["title"].startswith("MathQA: Towards interpretable math word problem solving")
    assert data["venue"].startswith("In Proceedings") and parse("Smith, J. (2019). A study of things. Journal of Studies, 4(2).")["title"] == "A study of things"


def test_identifiers_come_only_from_the_text_and_a_cut_off_doi_is_not_recorded():
    assert parse("A. Writer. A paper. doi: 10.2307/2334029, 1952.")["doi"] == "10.2307/2334029"
    assert parse("A. Writer. A paper. In EMNLP, doi: 10.18653/v1/")["doi"] is None  # a DOI wrapped at the line end is incomplete, so it is not guessed
    assert parse("A. Writer. A paper without any identifier. 2020.")["arxiv_id"] is None and parse("A. Writer. A paper. arXiv:1706.03762v5, 2017.")["arxiv_id"] == "1706.03762"


BIBLIOGRAPHY = """Michael Ahn, Anthony Brohan, Noah Brown, Yevgen Chebotar, Chelsea
Finn, Karol Hausman, et al. 2022. Do as I can, not as I say: Grounding language in robotic affordances. arXiv preprint arXiv:2204.01691.
Aida Amini, Saadia Gabriel, and Hannaneh
Hajishirzi. 2019. MathQA: Towards interpretable math word problem solving. In Proceedings of the 2019 Conference of the
Association for Computational Linguistics: Human Language Technologies, Minneapolis, Minnesota.
Tom Brown, Benjamin Mann, Nick Ryder, and others. 2020. Language models are few-shot learners. In NeurIPS.
Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian. 2021. Training verifiers to solve math word problems. arXiv:2110.14168.
Jason Wei, Xuezhi Wang, Dale Schuurmans. 2022. Chain of thought prompting elicits reasoning in large language models.
Tom Brown and Another Person. 2020. A second Brown paper from the same year. Journal of Things."""


def test_an_unnumbered_author_year_bibliography_is_split_into_its_entries():
    entries = author_year_entries(BIBLIOGRAPHY)
    assert [number for number, _ in entries] == [1, 2, 3, 4, 5, 6]
    assert entries[1][1].startswith("Aida Amini") and entries[1][1].endswith("Minnesota.") and "Hajishirzi. 2019." in entries[1][1]  # a wrapped entry stays one entry
    assert author_year_entries("Just a paragraph. 2020.\nAnother line.") == []  # not a bibliography


def paper_with(text):
    paper = SimpleNamespace(paragraphs=[Paragraph(1, "3 Experiments", text)], references=[PaperReference(n, t) for n, t in author_year_entries(BIBLIOGRAPHY)])
    return CitationExtractor().extract(paper)


def test_author_year_citations_are_matched_to_the_bibliography_without_guessing():
    paper = paper_with("As shown by (Wei et al., 2022; Cobbe et al., 2021) and by Amini et al. (2019), the method works (Ahn et al., 2022). "
                       "Brown and Person (2020) and (Brown et al., 2020) differ, while (Unknown et al., 2018) and (Smith, 1999) cite nothing we have.")
    assert sorted(c.reference_number for c in paper.citations) == [1, 2, 4, 5, 6]  # Brown and Person (6) is told apart by the second author; "(Brown et al., 2020)" fits two entries and is left out
    assert all(c.section == "3 Experiments" for c in paper.citations)
    ambiguous = author_year_numbers("(Brown, 2020)", author_year_index(paper))
    assert ambiguous == []  # two 2020 entries start with Brown: the citation is not attributed to either


def test_numbered_and_author_year_citations_can_coexist_and_the_bibliography_itself_is_not_counted():
    paper = SimpleNamespace(paragraphs=[Paragraph(1, "1 Introduction", "We follow [2] and (Wei et al., 2022)."), Paragraph(2, "References", "Wei et al. (2022) is listed here.")],
                            references=[PaperReference(n, t) for n, t in author_year_entries(BIBLIOGRAPHY)])
    assert sorted(c.reference_number for c in CitationExtractor().extract(paper).citations) == [2, 5]


@pytest.fixture(scope="module")
def analysed(tmp_path_factory):
    result = {}
    with pytest.MonkeyPatch.context() as patch:  # the session directory must not leak into the tests that run after this module
        patch.setenv("PREREQAI_SESSION_DIR", str(tmp_path_factory.mktemp("sessions")))
        session_manager.sessions.clear()
        for pid in ("chain-of-thought", "dpo"):
            outcome = platform.analyze(f"backend/prereqai_eval/benchmark/pdfs/{pid}.pdf")
            result[pid] = session_manager.get(outcome["session_id"]).paper
        session_manager.sessions.clear()
    return result


def test_chain_of_thought_yields_identifiable_citations_and_a_reading_list(analysed):
    paper = analysed["chain-of-thought"]
    assert len({c.reference_number for c in paper.citations}) > 30 and len(paper.references) >= 50  # was 0 citations and 5 "references" from a checklist
    items = build_reading_list(paper)
    assert items and all(item["title"] for item in items) and not any(item["title"].startswith("If you") for item in items)


# Hand-checked against the bibliography printed in the DPO PDF: (reference number, the title's opening words).
DPO_TITLES = {1: "training a helpful and harmless", 3: "pythia: a suite", 4: "generalized results for the existence", 5: "rank analysis of incomplete", 8: "sparks of artificial general",
              11: "palm: scaling language modeling", 14: "contextual dueling bandits", 17: "sequence tutor", 20: "reliability and learnability", 22: "reinforcement learning and control as",
              25: "cross-task generalization", 28: "training language models to follow", 31: "reinforcement learning by reward-weighted", 34: "is reinforcement learning (not)",
              37: "dueling rl", 40: "learning to summarize from human feedback", 43: "tl;dr: mining reddit", 46: "neural text generation with unlikelihood", 48: "learning to extract coherent",
              51: "fine-tuning language models from human preferences"}


def test_at_least_80_percent_of_twenty_hand_checked_dpo_titles_are_right(analysed):
    related = {item.reference_number: item for item in analysed["dpo"].related_papers}
    right = [n for n, opening in DPO_TITLES.items() if related[n].title.lower().startswith(opening)]
    assert len(DPO_TITLES) == 20 and len(right) >= 16, f"only {len(right)} of 20: wrong {sorted(set(DPO_TITLES) - set(right))}"
    assert related[4].arxiv_id == "2110.11487" and related[5].doi == "10.2307/2334029" and related[14].arxiv_id is None and related[14].doi is None  # identifiers only where the text has them
