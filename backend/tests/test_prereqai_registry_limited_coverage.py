"""The registry limit is real and documented: a concept outside the registry is not detected or invented, and the README says so."""
from pathlib import Path

import pymupdf

from backend.platform import platform

README = Path(__file__).resolve().parents[2] / "README.md"


def test_an_unregistered_concept_is_not_detected_and_registered_ones_are(tmp_path):
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "We use Zorblax Theory together with the Transformer and attention.", fontsize=6)
    path = tmp_path / "p.pdf"
    document.save(str(path))

    report = platform.analyze(str(path))["report"]
    names = {c["name"] if isinstance(c, dict) else c for c in report["concepts"]}

    assert "Transformer" in names
    assert not any("zorblax" in str(name).lower() for name in names)
    planned = {step["concept"] for step in report["learning_plan"]}
    assert not any("zorblax" in name.lower() for name in planned)


def test_the_readme_states_that_unregistered_concepts_are_not_detected():
    text = README.read_text(encoding="utf-8")
    assert "## Concept coverage" in text and "not in the registry is not detected" in text.replace("\n> ", " ")
