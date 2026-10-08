"""One analysis invocation never shares mutable state with another: the caller
owns its result (changing it changes neither the stored session nor the next
run), and two runs -- one after another or overlapping -- each return only
their own input's data, warnings and status."""
import json
from concurrent.futures import ThreadPoolExecutor

import pymupdf as fitz
import pytest

from backend.platform import AnalysisLimits, PreReqAIPlatform
from backend.session import session_manager


def _pdf(tmp_path, name, body):
    document = fitz.open()
    document.new_page().insert_text((72, 72), f"Paper {name}\n\nAbstract\n{body}\n\n1 Introduction\n{body}\n", fontsize=11)
    path = tmp_path / f"{name}.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _report(outcome):
    return json.dumps(outcome["report"], sort_keys=True, default=str)


@pytest.fixture
def papers(tmp_path):
    return (_pdf(tmp_path, "A", "We use softmax and attention and convolution and backpropagation."),
            _pdf(tmp_path, "B", "We use gradient descent and the Fourier transform."))


def _scribble(value):
    if isinstance(value, dict):
        for item in value.values():
            _scribble(item)
        value["__leak__"] = True
    elif isinstance(value, list):
        for item in value:
            _scribble(item)
        value.append("__leak__")


def test_changing_a_returned_result_changes_neither_its_session_nor_the_next_run(papers):
    platform = PreReqAIPlatform()
    first = platform.analyze(papers[0])
    expected = _report(first)

    _scribble(first["report"])
    second = platform.analyze(papers[0])

    assert "__leak__" not in json.dumps(session_manager.get(first["session_id"]).report, default=str)  # the session's own copy
    assert _report(second) == expected and second["session_id"] != first["session_id"]


def test_a_second_run_with_a_different_input_carries_only_its_own_data(papers):
    platform = PreReqAIPlatform()
    platform.analyze(papers[0], limits=AnalysisLimits(max_seconds=0.000001))  # stopped by a budget: its state must not stick
    first, second = platform.analyze(papers[0]), platform.analyze(papers[1])

    assert first["status"] == second["status"] == "success" and second["warnings"] == []
    assert _report(second) != _report(first) and _report(second) == _report(PreReqAIPlatform().analyze(papers[1]))


def test_overlapping_runs_each_return_only_their_own_result(papers):
    platform = PreReqAIPlatform()
    alone = {path: _report(PreReqAIPlatform().analyze(path)) for path in papers}

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(platform.analyze, papers * 3))

    assert [outcome["status"] for outcome in outcomes] == ["success"] * 6
    assert [_report(outcome) for outcome in outcomes] == [alone[path] for path in papers * 3]
    assert len({outcome["session_id"] for outcome in outcomes}) == 6
