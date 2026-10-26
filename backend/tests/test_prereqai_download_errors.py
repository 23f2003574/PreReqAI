"""A failed arXiv/DOI download says what happened (no such paper, server refusal, unreachable) and what to do, not an HTTP-library dump."""
import requests

from backend.platform.prereqai_platform import _stopped_outcome


def _http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.exceptions.HTTPError(f"{status} Client Error: for url: https://arxiv.org/pdf/9999.99999.pdf", response=response)


def test_missing_paper_names_the_identifier_problem():
    outcome = _stopped_outcome(_http_error(404))
    assert outcome["status"] == "failure"
    assert "No paper was found" in outcome["detail"] and "HTTP 404" in outcome["detail"]
    assert "typos" in outcome["hint"]
    assert "uploaded" not in outcome["detail"]


def test_server_refusal_says_to_retry_later():
    outcome = _stopped_outcome(_http_error(503))
    assert "HTTP 503" in outcome["detail"] and "Try again" in outcome["hint"]


def test_unreachable_server_hides_the_pool_dump_but_keeps_it_for_developers():
    raw = requests.exceptions.ConnectionError("HTTPSConnectionPool(host='arxiv.org', port=443): Max retries exceeded")
    outcome = _stopped_outcome(raw)
    assert "could not be reached" in outcome["detail"] and "HTTPSConnectionPool" not in outcome["detail"]
    assert "HTTPSConnectionPool" in outcome["error"]["message"]
    assert "network connection" in outcome["hint"]


def test_wrapped_http_error_is_still_recognised():
    wrapper = RuntimeError("download failed")
    wrapper.__cause__ = _http_error(404)
    assert "No paper was found" in _stopped_outcome(wrapper)["detail"]
