import json
from pathlib import Path

from backend.cli import main

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def test_human_summary_reports_readiness_difficulty_and_preparation_time(capsys):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]
    assert main(["prerequisites", "analyze", str(SAMPLE)]) == 0
    lines = capsys.readouterr().out.splitlines()

    ready, time = report["readiness"], report["study_time"]
    expected = (f"  readiness: {ready['status']} ({ready['completed_concepts']}/{ready['total_concepts']} concepts ready); "
                f"difficulty: {report['paper_difficulty']['level']}; "
                f"preparation: ~{time['total_hours']}h over {time['recommended_days']} days")
    assert expected in lines and len(lines) <= 5
