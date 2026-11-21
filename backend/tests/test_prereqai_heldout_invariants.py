"""The held-out gate: three CC BY papers the rules were not tuned on must satisfy invariants that need no annotation, offline, with clear messages when one fails."""
import hashlib
import json
import shutil
from types import SimpleNamespace

import pytest

from backend.models import Paper, PaperReference, PaperSection
from backend.prereqai_eval import gate, heldout

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def report():
    return heldout.run_heldout()


def test_the_manifest_records_source_licence_evidence_and_a_matching_sha256():
    papers = heldout.load_manifest()
    assert {p["arxiv_id"] for p in papers} == {"2305.13245", "2310.06825", "2212.08073"}
    for paper in papers:
        assert paper["license"]["spdx"] == "CC-BY-4.0" and paper["license"]["evidence_url"] == paper["source_url"] == f"https://arxiv.org/abs/{paper['arxiv_id']}"
        assert paper["license"]["verified_by"].startswith("Claude (AI assistant)") and "not a human reviewer" in paper["license"]["verified_by"]  # never presented as a human check
        with open(paper["pdf_path"], "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == paper["pdf"]["sha256"]


def test_a_changed_pdf_an_unverified_licence_or_a_missing_file_stops_the_gate_with_the_reason(tmp_path):
    shutil.copytree(heldout.HELDOUT_DIR, tmp_path / "heldout")
    manifest = tmp_path / "heldout" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    (tmp_path / "heldout" / "pdfs" / "gqa.pdf").write_bytes(b"%PDF-1.4 changed")
    data["papers"][1]["license"]["status"] = "unverified"
    (tmp_path / "heldout" / "pdfs" / "constitutional-ai.pdf").unlink()
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(heldout.HeldoutError) as error:
        heldout.load_manifest(manifest)
    text = " | ".join(error.value.problems)
    assert "gqa: the PDF does not match its recorded SHA-256" in text and "mistral-7b: the licence is not recorded as a verified CC-BY-4.0" in text and "constitutional-ai: the PDF pdfs/constitutional-ai.pdf is missing" in text
    checks = []
    assert gate.heldout_checks(checks, {}, manifest) is None and checks[0]["passed"] is False and "SHA-256" in checks[0]["detail"]


def test_every_invariant_holds_on_the_three_papers(report):
    assert report["passed"], heldout.render_heldout(report)
    assert set(report["invariants"]) == set(heldout.INVARIANTS) and all(share == 1.0 for share in report["invariants"].values())
    assert [row["id"] for row in report["papers"]] == ["gqa", "mistral-7b", "constitutional-ai"]


def test_the_references_of_each_paper_are_really_extracted():
    from backend.pipeline import ResearchPaperPipeline

    counts = {p["id"]: len(ResearchPaperPipeline().run(p["pdf_path"]).paper.references) for p in heldout.load_manifest()}
    assert counts["constitutional-ai"] == 25 and counts["gqa"] >= 20 and counts["mistral-7b"] >= 20


def _paper(**changes):
    from backend.ingestion import RawPage

    base = dict(references=[PaperReference(i, f"Author {i}. ({2000 + i}). A title.") for i in range(1, 12)],
                sections=[PaperSection(title="1 Introduction", content="We study softmax attention in transformer models."), PaperSection(title="References", content="x")],
                concepts=[], pages=[RawPage(page_number=1, text="We study softmax attention in transformer models.")])
    base.update(changes)
    paper = Paper(source_path="x.pdf", metadata=None)
    for key, value in base.items():
        setattr(paper, key, value)
    return paper


def test_each_invariant_names_its_violation_clearly():
    from backend.models import DetectedConcept

    assert not any(heldout.check_paper(_paper(), heldout.NO_FLOORS).values())
    missing = heldout.check_paper(_paper(references=[]), heldout.NO_FLOORS)["references_extracted"]
    assert missing and "only 0 bibliography entries were extracted (at least 10 expected)" in missing[0]
    duplicated = heldout.check_paper(_paper(sections=[PaperSection(title="Model", content="a"), PaperSection(title="3 Model", content="b"), PaperSection(title="Model", content="c")]), heldout.NO_FLOORS)
    assert duplicated["no_duplicate_headings"] == ["the heading 'Model' appears 2 times"]
    short = heldout.check_paper(_paper(sections=[PaperSection(title="2 Of", content="a"), PaperSection(title="Front Matter", content="b")]), heldout.NO_FLOORS)["no_short_headings"]
    assert short == ["the heading '2 Of' is shorter than 3 characters"]
    only_in_references = _paper(concepts=[DetectedConcept(name="Dropout", domain="deep_learning", occurrences=1)],
                                sections=[PaperSection(title="1 Introduction", content="We study sorting."), PaperSection(title="References", content="Srivastava. Dropout: a simple way.")])
    assert heldout.check_paper(only_in_references, heldout.NO_FLOORS)["no_bibliography_only_concepts"] == ["the concept 'Dropout' is detected but no term of it occurs outside the bibliography"]
    assert not heldout.check_paper(_paper(concepts=[DetectedConcept(name="Softmax", domain="transformers", occurrences=1)]), heldout.NO_FLOORS)["no_bibliography_only_concepts"]


def test_an_evidence_quotation_that_is_not_on_its_page_is_reported(monkeypatch):
    passage = {"passage_id": "p-1", "sentence": "A sentence the page does not hold.", "page_number": 1, "section": "1 Introduction", "concepts": []}
    monkeypatch.setattr("backend.evidence.build_evidence", lambda paper: {"Softmax": [passage, {**passage, "passage_id": "p-2", "page_number": 9}, {**passage, "passage_id": "p-3", "sentence": "We study softmax attention", "section": "9 Nowhere"}]})
    found = heldout.check_paper(_paper(), heldout.NO_FLOORS)["evidence_quotations_verified"]
    assert len(found) == 3 and "is not on page 1" in found[0] and "page 9, which the paper does not have" in found[1] and "names the section '9 Nowhere'" in found[2]


def test_the_gate_turns_a_violation_into_a_failed_check_with_what_to_look_at(monkeypatch):
    broken = {"passed": False, "invariants": {name: 1.0 for name in heldout.INVARIANTS},
              "papers": [{"id": "gqa", "violations": {name: [] for name in heldout.INVARIANTS}, "self_test": {"no concepts": True}}]}
    broken["invariants"]["no_duplicate_headings"] = 0.5
    broken["papers"][0]["violations"]["no_duplicate_headings"] = ["the heading 'Model' appears 2 times"]
    monkeypatch.setattr(heldout, "run_heldout", lambda manifest=None: broken)
    checks = []
    gate.heldout_checks(checks, {name: 1.0 for name in heldout.INVARIANTS})
    failed = [c for c in checks if not c["passed"]]
    assert [c["metric"] for c in failed] == ["no_duplicate_headings"] and failed[0]["detail"] == "gqa: the heading 'Model' appears 2 times" and failed[0]["group"] == "heldout_invariants"


def test_the_gate_includes_the_held_out_group_and_says_the_licences_were_not_read_by_a_human(report):
    checks = []
    held = gate.heldout_checks(checks, gate.load_thresholds()["heldout_invariants"])
    assert held and all(c["passed"] for c in checks) and len(checks) == 7
    lines = gate.render_gate({"passed": True, "checks": checks, "heldout": {"papers": [{k: row[k] for k in ("id", "arxiv_id", "licence", "licence_checked_by", "sha256", "ok")} for row in report["papers"]]},
                              "real_papers": {"status": "provisional", "per_paper": []}})
    assert "not a human reviewer" in lines and "held-out constitutional-ai" in lines
    assert "heldout_invariants" in gate.THRESHOLDS.read_text(encoding="utf-8")


def test_the_check_needs_no_network(monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("the held-out gate must work offline")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    assert heldout.run_heldout()["passed"]


def _informative_paper():
    """A small synthetic paper that satisfies every floor, to be damaged."""
    from backend.ingestion import RawPage
    from backend.models import Citation, DetectedConcept

    abstract = "We study attention. " * 12
    body = "The Transformer uses softmax attention over the tokens of the input sequence in every layer of the network."
    sections = [PaperSection(title="Abstract", content=abstract), PaperSection(title="1 Introduction", content=body), PaperSection(title="2 Method", content=body),
                PaperSection(title="3 Results", content=body), PaperSection(title="References", content="x")]
    return _paper(sections=sections, concepts=[DetectedConcept(name=n, domain="transformers", occurrences=2) for n in ("Softmax", "Attention", "Transformer")],
                  citations=[Citation(1, 1, "as in [1]", "1 Introduction"), Citation(2, 2, "as in [2]", "2 Method")],
                  pages=[RawPage(page_number=1, text="A Good Title Here\nAbstract\n" + abstract + body + body + body)],
                  metadata=SimpleNamespace(title="A Good Title Here"))


def test_an_empty_extraction_no_longer_passes_the_invariants(monkeypatch):
    monkeypatch.setattr("backend.evidence.build_evidence", lambda paper: {"Softmax": [{"passage_id": f"p-{i}", "sentence": "The Transformer uses softmax attention over the tokens of the input sequence in every layer of the network.",
                                                                                      "page_number": 1, "section": "1 Introduction", "concepts": []} for i in range(3)]})
    good = _informative_paper()
    assert not any(heldout.check_paper(good).values()), heldout.check_paper(good)
    empty = _paper(sections=[], concepts=[], references=[], pages=[])
    found = heldout.check_paper(empty, expected_title="Some Paper Title")
    assert len(found["informative_extraction"]) >= 5 and "only 0 concepts were detected (at least 3 expected)" in found["informative_extraction"]
    assert "no title was found in the PDF metadata or on page 1" in found["informative_extraction"]


def test_the_self_test_proves_each_kind_of_damage_is_reported(monkeypatch):
    monkeypatch.setattr("backend.evidence.build_evidence", lambda paper: {"Softmax": [{"passage_id": f"p-{i}", "sentence": "The Transformer uses softmax attention over the tokens of the input sequence in every layer of the network.",
                                                                                      "page_number": 1, "section": "1 Introduction", "concepts": []} for i in range(3)]} if paper.sections else {})
    good = _informative_paper()
    assert not any(heldout.check_paper(good).values())
    caught = heldout.self_test(good)
    assert set(caught) == set(heldout.degradations()) and all(caught.values()), caught
    monkeypatch.setattr(heldout, "check_paper", lambda *args, **kwargs: {name: [] for name in heldout.INVARIANTS})  # a gate that cannot fail is exposed
    assert not any(heldout.self_test(good).values())


def test_a_paper_may_set_stricter_floors_and_the_gate_fails_when_the_self_test_misses(monkeypatch):
    assert heldout.check_paper(_informative_paper(), {**heldout.DEFAULT_FLOORS, "concepts": 9}, "")["informative_extraction"][0].startswith("only 3 concepts")
    report = {"passed": False, "invariants": {name: 1.0 for name in heldout.INVARIANTS}, "papers": [{"id": "gqa", "violations": {name: [] for name in heldout.INVARIANTS}, "self_test": {"no concepts": False}}]}
    monkeypatch.setattr(heldout, "run_heldout", lambda manifest=None: report)
    checks = []
    gate.heldout_checks(checks, {})
    assert [c["metric"] for c in checks if not c["passed"]] == ["gate_detects_degradation"] and "no concepts was not reported" in checks[-1]["detail"]
