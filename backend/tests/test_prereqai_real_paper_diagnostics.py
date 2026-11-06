"""The live-paper check (opt-in, needs arXiv) explains why a run failed instead of dumping the raw outcome. This test is offline."""
import pytest

from backend.api.workflow_result import failure_body
from backend.tests.test_prereqai_real_paper_live import explain_failure

pytestmark = pytest.mark.prereqai


def test_a_successful_outcome_needs_no_explanation():
    assert explain_failure({"status": "success"}) == ""


def test_a_failure_names_the_stage_the_message_and_the_hint():
    outcome = failure_body("concept_detector", "Failed to process the paper", error=KeyError("x"), hint="Report this bug.")
    text = explain_failure(outcome)
    assert "arXiv:1706.03762" in text and "'concept_detector'" in text
    assert "Failed to process the paper" in text and "Hint: Report this bug." in text


def test_an_unreachable_server_points_at_network_access():
    outcome = failure_body("analysis", "arXiv could not be reached after 3 attempts", hint="Try again later.")
    assert "network access to arxiv.org" in explain_failure(outcome)
