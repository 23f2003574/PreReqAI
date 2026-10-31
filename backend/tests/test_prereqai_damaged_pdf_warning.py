"""A PDF cut short mid-download is repaired by the reader and analysed as a shorter paper; the result must say so."""
from pathlib import Path

import pytest

from backend.platform.prereqai_platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def _warnings(path):
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["status"] == "success"
    return outcome["warnings"]


def test_a_truncated_pdf_still_analyses_but_warns_that_it_was_damaged(tmp_path):
    cut = tmp_path / "cut.pdf"
    cut.write_bytes(SAMPLE.read_bytes()[: SAMPLE.stat().st_size // 2])
    assert any("damaged" in warning for warning in _warnings(cut))


def test_an_intact_pdf_has_no_damage_warning():
    assert not any("damaged" in warning for warning in _warnings(SAMPLE))
