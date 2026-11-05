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


def test_platform_words_warnings_with_the_labels_its_caller_gives():
    """The wording belongs to the caller (CLI flags by default, form fields for HTTP), not to a rewrite of the platform's text."""
    from backend.platform import PreReqAIPlatform
    import inspect

    default = inspect.signature(PreReqAIPlatform.analyze).parameters["labels"].default
    assert default == ("--known", "--studied")
