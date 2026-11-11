"""Section titles keep their number ("4 Experiments"), but the experiment extractor compared the whole title to three bare names, so the
Experiments/Results sections of a numbered paper (nearly every paper) were never promoted to experiments."""
import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.parsing import ExperimentExtractor, ScientificSectionParser


def _experiments(text):
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    paper = ScientificSectionParser().parse(document)
    return [(e.title, e.description, e.section) for e in ExperimentExtractor().extract(paper).experiments]


@pytest.mark.parametrize("title", [
    "4 Experiments", "5. Results", "3.2 Experimental Setup", "IV. Experimental Results", "Experiments", "6 Experimental Evaluation",
    "5 Results and Discussion", "4 Experiments and Results",
])
def test_numbered_and_unnumbered_experiment_sections_are_promoted(title):
    assert _experiments(f"1 Introduction\nIntro.\n{title}\nWe train it.\n") == [(title, "We train it.", title)]


@pytest.mark.parametrize("title", ["1 Introduction", "2 Related Work", "3 Method", "7 Conclusion"])
def test_other_sections_are_not_experiments(title):
    assert _experiments(f"{title}\nText.\n") == []
