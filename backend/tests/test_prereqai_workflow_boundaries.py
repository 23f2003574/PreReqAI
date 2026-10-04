"""Input/output boundaries of the PreReqAI analysis workflow: which input forms
are recognised, that an existing local PDF is never mistaken for a DOI or arXiv
source because of its path, and what a successful result carries."""
import json

import fitz
import pytest

from backend.cli import EXIT_OK, main
from backend.ingestion.research_source_detector import ResearchSourceDetector
from backend.platform import platform


def _write_pdf(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe use softmax and attention.\n\n1 Introduction\nWe use softmax.\n", fontsize=11)
    path.write_bytes(document.tobytes())
    return path


def test_an_existing_local_pdf_is_a_local_pdf_even_when_its_path_looks_like_a_doi_or_arxiv_id(tmp_path):
    detector = ResearchSourceDetector()
    for relative in ("papers/10.1145/3292500.pdf", "arxiv.org/abs/1706.03762/paper.pdf"):
        path = _write_pdf(tmp_path / relative)

        source = detector.detect(str(path))

        assert (source.source_type, source.identifier) == ("pdf", str(path)), relative
        assert platform.analyze(str(path))["status"] == "success"


def test_the_same_local_pdf_succeeds_through_the_cli_when_its_path_contains_a_doi(tmp_path, capsys):
    path = _write_pdf(tmp_path / "10.1145" / "paper.pdf")

    assert main(["prerequisites", "analyze", str(path)]) == EXIT_OK
    assert capsys.readouterr().out.startswith("Analysed '")


def test_equivalent_forms_the_detector_already_supports_are_normalised(tmp_path):
    path = _write_pdf(tmp_path / "Paper.PDF")  # upper-case extension

    for given in (str(path), f"  {path}\n"):  # surrounding whitespace
        source = ResearchSourceDetector().detect(given)
        assert (source.source_type, source.identifier) == ("pdf", str(path))
        assert platform.analyze(given)["status"] == "success"


@pytest.mark.parametrize(
    "given,source_type,identifier",
    [("https://arxiv.org/abs/1706.03762", "arxiv", "1706.03762"), ("10.1000/xyz123", "doi", "10.1000/xyz123"),
     ("https://doi.org/10.1000/xyz123", "doi", "10.1000/xyz123")],
)
def test_arxiv_and_doi_inputs_are_still_detected_by_form(given, source_type, identifier):
    source = ResearchSourceDetector().detect(given)

    assert (source.source_type, source.identifier) == (source_type, identifier)


def test_a_doi_input_fails_through_the_result_contract_because_doi_resolution_is_not_implemented():
    outcome = platform.analyze("10.1000/xyz123")

    assert outcome["status"] == "failure" and outcome["stage"] == "analysis"
    assert "doi resolution has not been implemented" in outcome["detail"] and outcome["error"]["type"] == "NotImplementedError"


def test_a_successful_result_carries_what_the_cli_and_api_surfaces_use(tmp_path):
    outcome = platform.analyze(str(_write_pdf(tmp_path / "paper.pdf")))

    report = outcome["report"]
    assert outcome["status"] == "success" and outcome["session_id"] and outcome["warnings"] == []
    assert report["paper"]["title"] and isinstance(report["concepts"], list)
    assert isinstance(report["prerequisites"], list) and isinstance(report["missing_prerequisites"], list)
    assert json.loads(json.dumps(outcome, default=str))["session_id"] == outcome["session_id"]
