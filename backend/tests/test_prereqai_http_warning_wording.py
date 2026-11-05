"""HTTP analyze warnings name the `known` / `studied` form fields, not the command-line flags the platform words them for."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

PAPER = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def _analyze(**data):
    with open(PAPER, "rb") as handle:
        response = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data)
    assert response.status_code == 200
    return response.json()["warnings"]


def test_unknown_names_are_reported_against_the_form_fields():
    warnings = _analyze(studied=["Nonsense"], known=["Typo"])
    assert warnings == ["`known` 'Typo' is not in this paper's study plan and was ignored",
                        "`studied` 'Nonsense' is not in this paper's study plan and was ignored"]


def test_a_studied_name_that_is_also_known_is_reported_against_the_form_fields():
    (warning,) = _analyze(studied=["calculus"], known=["calculus"])
    assert warning.startswith("`studied` 'calculus' was ignored because you also said you already know it")


def test_a_request_without_problems_has_no_warnings():
    assert _analyze(studied=["Calculus"]) == []



def _platform_warnings(**kwargs):
    from backend.platform import PreReqAIPlatform

    outcome = PreReqAIPlatform().analyze(str(PAPER), **kwargs)
    assert outcome["status"] == "success"
    return outcome["warnings"]


def test_platform_defaults_to_command_line_flag_names():
    assert _platform_warnings(known=["Typo"], studied=["Nonsense"]) == [
        "--known 'Typo' is not in this paper's study plan and was ignored",
        "--studied 'Nonsense' is not in this paper's study plan and was ignored",
    ]


def test_platform_uses_the_labels_its_caller_supplies():
    warnings = _platform_warnings(known=["Typo"], studied=["Nonsense"], labels=("the 'k' field", "the 's' field"))
    assert warnings == [
        "the 'k' field 'Typo' is not in this paper's study plan and was ignored",
        "the 's' field 'Nonsense' is not in this paper's study plan and was ignored",
    ]


def test_labels_do_not_change_an_analysis_that_has_nothing_to_warn_about():
    assert _platform_warnings(labels=("`known`", "`studied`")) == _platform_warnings()
