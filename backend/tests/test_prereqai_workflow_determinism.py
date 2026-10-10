"""The same paper and configuration give the same public result every time --
within one process and across processes with different hash seeds. Only the
intentionally volatile fields differ: the session_id (a fresh id per run) and
wall-clock durations."""
import json
import os
import subprocess
import sys

import pymupdf as fitz

from backend.platform import AnalysisLimits, PreReqAIPlatform

BODY = ("We use softmax, attention, convolution, gradient descent, backpropagation, linear algebra, "
        "probability, matrix multiplication and the Fourier transform in neural networks.")
VOLATILE_DIAGNOSTICS = ("stage_seconds", "total_seconds", "slowest_stage")


def _pdf(tmp_path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), f"Attention Is All You Need\n\nAbstract\n{BODY}\n\n1 Introduction\n{BODY}\n\n2 Method\nWe use softmax and attention.\n", fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return str(path)


def _semantic(outcome):
    """The public result without its volatile fields (timings keep their stage names and order)."""
    stable = {key: value for key, value in outcome.items() if key not in ("session_id", "timings")}
    stable["timing_stages"] = list(outcome.get("timings", {}))
    if "diagnostics" in outcome:
        stable["diagnostics"] = {k: v for k, v in outcome["diagnostics"].items() if k not in VOLATILE_DIAGNOSTICS}
    return json.dumps(stable)


def _run(paper):
    return PreReqAIPlatform().analyze(paper, diagnostics=True, limits=AnalysisLimits(max_seconds=600))


def test_two_equivalent_runs_give_the_same_public_result(tmp_path):
    paper = _pdf(tmp_path)

    first, second = _run(paper), _run(paper)

    assert first["status"] == "success" and first["report"]["concepts"] and first["report"]["prerequisites"]
    assert _semantic(first) == _semantic(second)
    assert first["session_id"] != second["session_id"]  # the one intentionally fresh value


def test_runs_in_processes_with_different_hash_seeds_agree(tmp_path):
    paper = _pdf(tmp_path)
    script = ("import json, sys; sys.path.insert(0, '.'); from backend.tests.test_prereqai_workflow_determinism import _run, _semantic; "
              f"print(_semantic(_run({paper!r})))")
    outputs = {subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True,
                              env={**os.environ, "PYTHONHASHSEED": seed}).stdout.strip().splitlines()[-1]
               for seed in ("0", "1", "12345")}

    assert outputs == {_semantic(_run(paper))}
