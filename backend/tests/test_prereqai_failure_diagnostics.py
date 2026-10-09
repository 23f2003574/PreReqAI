"""An unexpected failure inside the analysis names the stage that broke, without --diagnose and without
touching the original error, and stops blaming the user's file; input failures keep their file hints."""
import json
from pathlib import Path

from backend.cli import main
from backend.platform import platform

SAMPLE = str(Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf")


def test_an_internal_stage_failure_names_the_stage_and_keeps_the_cause(monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise KeyError("Linear Algebra")

    monkeypatch.setattr(platform.analysis.concept_detector, "detect", broken)

    assert main(["prerequisites", "analyze", SAMPLE, "--json"]) == 1
    outcome = json.loads(capsys.readouterr().out)

    assert outcome["status"] == "failure" and outcome["stage"] == "analysis"
    assert "(in analysis stage 'concept_detector')" in outcome["detail"]
    assert outcome["error"] == {"type": "KeyError", "message": "'Linear Algebra'"}  # the original cause, untouched
    assert "concept_detector" in outcome["hint"] and "--diagnose" in outcome["hint"] and "Upload" not in outcome["hint"]
    assert str(Path(SAMPLE).parent) not in json.dumps(outcome)  # no path or paper content added to the message


def test_a_bad_input_file_keeps_the_file_hint_and_has_no_stage_suffix(tmp_path, capsys):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")

    assert main(["prerequisites", "analyze", str(broken), "--json"]) == 1
    outcome = json.loads(capsys.readouterr().out)

    assert "analysis stage" not in outcome["detail"] and outcome["hint"] == "Upload a text-based PDF research paper."
