import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "prerequisites" / "sample-paper.pdf"


def _analyze_json(path):
    # A fresh process: MuPDF writes its diagnostics straight to the process's stdout, which an in-process capture does not see.
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", str(path), "--json"],
                          cwd=ROOT, capture_output=True, text=True)


def test_a_damaged_pdf_keeps_json_output_parseable_and_still_warns(tmp_path):
    data = SAMPLE.read_bytes()
    path = tmp_path / "cut.pdf"
    path.write_bytes(data[: len(data) // 2])  # an interrupted download: MuPDF repairs it and prints diagnostics
    result = _analyze_json(path)
    assert result.returncode == 0
    outcome = json.loads(result.stdout)
    assert outcome["status"] == "success"
    assert any("damaged" in warning for warning in outcome["warnings"])


def test_an_intact_pdf_json_output_is_unchanged():
    result = _analyze_json(SAMPLE)
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "success"
