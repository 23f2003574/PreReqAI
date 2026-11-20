"""Bibliographies whose entries open with a bracketed author-year label ("[Askell et al., 2021] ...") are extracted, and the paper's citations are linked to them."""
import re

import pytest

from backend.models import Paper, PaperReference
from backend.parsing.citation_extractor import CitationExtractor, _surname
from backend.parsing.reference_extractor import ReferenceExtractor, bracketed_author_year_entries
from backend.parsing.reference_metadata_parser import ReferenceMetadataParser

pytestmark = pytest.mark.prereqai
BIBLIOGRAPHY = """[Askell et al., 2021] Askell, A., Bai, Y., Chen, A., and Kaplan, J. (2021). A general
language assistant as a laboratory for alignment.
[Bai et al., 2022] Bai, Y., Jones, A., Ndousse, K., and Kaplan, J. (2022). Training a helpful and
harmless assistant with reinforcement learning from human feedback.
[Bowman et al., 2022] Bowman, S. R., Hyun, J., Perez, E., and Kaplan, J. (2022) Measuring progress on
scalable oversight for large language models.
[Cobbe and Kosaraju, 2021] Cobbe, K. and Kosaraju, V. (2021). Training verifiers to solve math word problems.
[Wei et al., 2022] Wei, J., Wang, X., Schuurmans, D., and Zhou, D. (2022). Chain of thought prompting
elicits reasoning in large language models.
[Wei et al., 2022b] Wei, J., Tay, Y., Bommasani, R., and Fedus, W. (2022). Emergent abilities of large language models.
"""


def _paper(text=BIBLIOGRAPHY, citing=()):
    from backend.models import Paragraph, PaperSection

    paper = Paper(source_path="x.pdf", metadata=None)
    paper.sections = [PaperSection(title="References", content=text)]
    paper.paragraphs = [Paragraph(i, "3 Method", sentence) for i, sentence in enumerate(citing, start=1)]
    return paper


def test_bracketed_entries_are_split_numbered_by_position_and_keep_their_label():
    entries = bracketed_author_year_entries(BIBLIOGRAPHY)
    assert [(n, label) for n, _, label in entries] == [(1, "Askell et al., 2021"), (2, "Bai et al., 2022"), (3, "Bowman et al., 2022"), (4, "Cobbe and Kosaraju, 2021"),
                                                      (5, "Wei et al., 2022"), (6, "Wei et al., 2022b")]
    references = ReferenceExtractor().extract(_paper()).references
    assert [r.reference_number for r in references] == [1, 2, 3, 4, 5, 6] and references[0].label == "Askell et al., 2021"
    assert references[0].raw_text.startswith("Askell, A., Bai, Y.") and "[Askell" not in references[0].raw_text


def test_metadata_is_parsed_from_the_entry_not_invented():
    parser = ReferenceMetadataParser()
    bowman = parser.parse(ReferenceExtractor().extract(_paper()).references[2].raw_text)
    assert _surname(bowman["authors"][0]) == "bowman" and bowman["year"] == 2022 and bowman["title"] == "Measuring progress on scalable oversight for large language models"


def test_fewer_than_five_labelled_entries_or_numbered_lists_are_not_bracketed_author_year():
    assert bracketed_author_year_entries("[Askell et al., 2021] A.\n[Bai et al., 2022] B.\n") == []
    numbered = ReferenceExtractor().extract(_paper("\n".join(f"[{n}] Author, A. ({2000 + n}). Title {n}." for n in range(1, 7)))).references
    assert [r.reference_number for r in numbered] == [1, 2, 3, 4, 5, 6] and all(r.label == "" for r in numbered)


def test_bracketed_and_narrative_citations_are_linked_to_the_right_entries():
    paper = ReferenceExtractor().extract(_paper(citing=[
        "Models learn this [Bai et al., 2022] and [Askell et al., 2021, Cobbe and Kosaraju, 2021].",
        "Wei et al. [2022] show chain of thought; see also Bowman et al. (2022).",
        "A year alone [2022] or an unknown author [Nobody et al., 2020] cites nothing, and [0] is not an entry.",
    ]))
    paper = CitationExtractor().extract(paper)
    assert [c.reference_number for c in paper.citations] == [2, 1, 4, 3]  # "Wei et al. [2022]" fits two entries (2022, 2022b) and is not guessed; the year alone, an unknown author and "[0]" cite nothing
    assert all(c.section == "3 Method" for c in paper.citations)


def test_constitutional_ai_references_and_citations(tmp_path):
    from pathlib import Path

    from backend.pipeline import ResearchPaperPipeline

    pdf = Path("backend/prereqai_eval/heldout/pdfs/constitutional-ai.pdf")
    if not pdf.exists():
        pytest.fail("the held-out PDFs are part of the repository")
    paper = ResearchPaperPipeline().run(str(pdf)).paper
    parser = ReferenceMetadataParser()
    assert len(paper.references) == 25  # the paper's own list: 25 entries (counted independently from the PDF's "(year)." marks); there is no longer list to find
    for reference in paper.references:
        data = parser.parse(reference.raw_text)
        assert _surname(data["authors"][0]) == reference.label.split()[0].lower().rstrip(",") and data["year"] == int(re.search(r"\d{4}", reference.label).group()) and data["title"]
    assert len(paper.citations) > 40 and {c.reference_number for c in paper.citations} <= {r.reference_number for r in paper.references}
