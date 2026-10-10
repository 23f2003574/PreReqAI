"""The paper input reaches the workflow in one canonical form: equivalent
spellings of a reference give the same source, meaningful parts the user gave
(an arXiv version, a DOI's case, a path) are kept exactly, and anything
malformed or ambiguous is rejected as a failure rather than guessed."""
import pytest

from backend.ingestion import ResearchSourceDetector
from backend.platform import PreReqAIPlatform

detect = ResearchSourceDetector().detect


def test_the_canonical_arxiv_link_gives_its_identifier():
    source = detect("https://arxiv.org/abs/1706.03762")

    assert (source.source_type, source.identifier) == ("arxiv", "1706.03762")


@pytest.mark.parametrize("alternate", [
    "  https://arxiv.org/abs/1706.03762\n", "http://www.arxiv.org/abs/1706.03762", "arxiv.org/pdf/1706.03762",
    "https://arxiv.org/pdf/1706.03762.pdf", "https://ARXIV.org/abs/1706.03762/",
])
def test_equivalent_arxiv_spellings_give_the_same_source(alternate):
    source = detect(alternate)

    assert (source.source_type, source.identifier) == ("arxiv", "1706.03762")
    assert source.original_input == alternate.strip()


@pytest.mark.parametrize("alternate", ["10.1145/3292500.3330701", "doi:10.1145/3292500.3330701",
                                       "https://doi.org/10.1145/3292500.3330701", "http://dx.doi.org/10.1145/3292500.3330701"])
def test_equivalent_doi_spellings_give_the_same_source(alternate):
    source = detect(alternate)

    assert (source.source_type, source.identifier) == ("doi", "10.1145/3292500.3330701")


def test_meaningful_parts_of_the_input_are_kept_exactly(tmp_path):
    assert detect("https://arxiv.org/abs/1706.03762v5").identifier == "1706.03762v5"  # was silently dropped
    assert detect("https://arxiv.org/pdf/1706.03762v2.pdf").identifier == "1706.03762v2"
    assert detect("https://doi.org/10.1038/S41586-020-2649-2").identifier == "10.1038/S41586-020-2649-2"
    paper = tmp_path / "10.1145" / "My Paper.PDF"
    paper.parent.mkdir()
    paper.write_bytes(b"%PDF-1.4")
    assert (detect(f" {paper} ").source_type, detect(str(paper)).identifier) == ("pdf", str(paper))


@pytest.mark.parametrize("malformed", [
    "", "   ", "not a paper", "1706.03762", "https://arxiv.org/abs/",
    "see https://arxiv.org/abs/1706.03762 and 10.1000/xyz",  # two references: ambiguous, was guessed as arXiv
    "random text 10.1000/abc here",  # a DOI inside prose, was guessed as a DOI
    "https://arxiv.org/abs/1706.03762 extra",
])
def test_malformed_or_ambiguous_input_is_rejected(malformed):
    with pytest.raises(ValueError, match="Unsupported research source"):
        detect(malformed)


def test_rejected_input_is_a_workflow_failure_before_any_later_stage():
    outcome = PreReqAIPlatform().analyze("see https://arxiv.org/abs/1706.03762 and 10.1000/xyz", diagnostics=True)

    assert outcome["status"] == "failure" and outcome["error"]["type"] == "ValueError"
    assert outcome["diagnostics"]["failed_stage"] == "source_detector" and outcome["diagnostics"]["completed_stages"] == []
