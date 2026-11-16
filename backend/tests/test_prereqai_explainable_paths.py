"""Explainable learning paths: ordering, direct versus transitive, deduplication, known and studied subjects, cycles, resources and the CLI, API and web."""
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient

from backend import cli
from backend.main import app
from backend.platform import platform
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.prerequisite_paths import KNOWN_REASON, build_paths
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
RULES = {"Top": ["Mid", "Side"], "Other": ["Mid"], "Mid": ["Base"], "Side": ["Base"], "Base": ["Root"]}
HOURS = {name: 2 for name in ("Mid", "Side", "Base", "Root")}


def _paper(concepts=("Top", "Other"), studied=(), known=(), resources=()):
    return N(concepts=[N(name=c) for c in concepts], study_progress=[N(concept=c, completed=True) for c in studied],
             missing_prerequisites=[N(concept=c, reason=KNOWN_REASON) for c in known],
             learning_resources=[N(concept=c, title=f"{c} course", provider="P", url=f"https://example.org/{c}", estimated_hours=3) for c in resources])


def _steps(result, root):
    return next(p["steps"] for p in result["paths"] if p["concept"] == root)


def test_a_multi_level_chain_is_ordered_foundations_first_with_direct_and_transitive_steps():
    steps = _steps(build_paths(_paper(), RULES, HOURS), "Top")
    assert [s["concept"] for s in steps] == ["Root", "Base", "Mid", "Side"]  # never a subject before one it needs
    assert {s["concept"]: s["relation"] for s in steps} == {"Root": "transitive", "Base": "transitive", "Mid": "direct", "Side": "direct"}
    root = steps[0]
    assert root["chain"] == ["Top", "Mid", "Base", "Root"] or root["chain"] == ["Top", "Side", "Base", "Root"]
    assert root["reason"] == "Base needs Root (PreReqAI's prerequisite table)" and root["estimated_hours"] == 2


def test_shared_prerequisites_appear_once_in_the_combined_path_with_everything_that_needs_them():
    combined = build_paths(_paper(), RULES, HOURS)["combined"]
    assert [c["concept"] for c in combined] == ["Root", "Base", "Mid", "Side"] and [c["order"] for c in combined] == [1, 2, 3, 4]
    mid = next(c for c in combined if c["concept"] == "Mid")
    assert mid["direct_for"] == ["Top", "Other"] and next(c for c in combined if c["concept"] == "Root")["transitive_for"] == ["Top", "Other"]
    position = {c["concept"]: c["order"] for c in combined}
    assert all(position[child] < position[name] for name in position for child in RULES.get(name, []) if child in position)


def test_known_and_studied_subjects_are_excluded_and_reported_but_their_own_prerequisites_remain():
    result = build_paths(_paper(studied=["Mid"], known=["Side"]), RULES, HOURS)
    assert [s["concept"] for s in _steps(result, "Top")] == ["Root", "Base"]
    assert result["excluded"] == [{"concept": "Mid", "why": "studied"}, {"concept": "Side", "why": "known"}]
    assert [c["concept"] for c in build_paths(_paper(studied=["Root", "Base", "Mid", "Side"]), RULES, HOURS)["combined"]] == []


def test_a_cycle_is_cut_and_reported_without_looping():
    result = build_paths(_paper(["A"]), {"A": ["B"], "B": ["C"], "C": ["A", "D"]}, {"B": 1, "C": 1, "D": 1})
    assert [s["concept"] for s in _steps(result, "A")] == ["D", "C", "B"]
    assert result["problems"] == ["cycle in the prerequisite table: A -> B -> C -> A"]


def test_invalid_references_missing_hours_and_concepts_without_rules_are_reported():
    result = build_paths(_paper(["A", "Lonely"]), {"A": ["B", "", "NoHours"], "B": []}, {"B": 1})
    assert any("invalid prerequisite ''" in p for p in result["problems"])
    assert any("NoHours (needed by A) has no study hours" in p for p in result["problems"])
    assert "no prerequisite rule for Lonely, so its prerequisites are unknown" in result["problems"]
    assert [s["concept"] for s in _steps(result, "A")] == ["B", "NoHours"]  # still shown, with no hours


def test_resources_sit_against_the_right_concepts_and_missing_ones_are_none():
    combined = {c["concept"]: c for c in build_paths(_paper(resources=["Base", "Side"]), RULES, HOURS)["combined"]}
    assert combined["Base"]["resource"]["url"] == "https://example.org/Base" and combined["Side"]["resource"]["title"] == "Side course"
    assert combined["Root"]["resource"] is None and combined["Mid"]["resource"] is None


def test_the_paths_are_deterministic_and_use_the_real_prerequisite_table():
    first = build_paths(_paper(["Top"]), RULES, HOURS)
    assert first == build_paths(_paper(["Top"]), RULES, HOURS)
    real = build_paths(N(concepts=[N(name="Transformer")], study_progress=[], missing_prerequisites=[], learning_resources=[]))
    names = [c["concept"] for c in real["combined"]]
    assert set(names) <= set(PrerequisiteDetector.PREREQUISITE_RULES) | {c for v in PrerequisiteDetector.PREREQUISITE_RULES.values() for c in v}
    assert names.index("Linear Algebra") < names.index("Attention") < names.index("Transformer") if "Transformer" in names else names.index("Linear Algebra") < names.index("Attention")
    assert real["problems"] == []


client = TestClient(app)


def _report(tmp_path, monkeypatch, **options):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    return platform.analyze(SAMPLE, **options)


def test_the_report_marks_known_studied_and_resources_and_leaves_the_recommendations_unchanged(tmp_path, monkeypatch):
    plain = _report(tmp_path, monkeypatch)["report"]
    shaped = _report(tmp_path, monkeypatch, known=["Linear Algebra"], studied=["Probability"])["report"]
    paths = shaped["study_paths"]
    assert {e["concept"]: e["why"] for e in paths["excluded"]} == {"Linear Algebra": "known", "Probability": "studied"}
    assert all(c["concept"] not in ("Linear Algebra", "Probability") for c in paths["combined"])
    resourced = {r["concept"]: r["url"] for r in shaped["learning_resources"]}
    assert all((c["resource"] or {}).get("url") == resourced.get(c["concept"]) for c in paths["combined"])
    assert [p["concept"] for p in plain["prerequisites"]] == [p["concept"] for p in shaped["prerequisites"]]  # recommendations are not affected
    assert plain["study_paths"]["problems"] == []


def test_progress_changes_refresh_the_paths_and_the_api_and_cli_agree(tmp_path, monkeypatch, capsys):
    sid = _report(tmp_path, monkeypatch)["session_id"]
    assert "Calculus" in [c["concept"] for c in platform.analyze(SAMPLE)["report"]["study_paths"]["combined"]]
    done = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"}).json()
    assert "study_paths" not in done  # the progress responses keep their own keys
    paths = client.get(f"/api/session/{sid}").json()["study_paths"]
    assert "Calculus" not in [c["concept"] for c in paths["combined"]] and {"concept": "Calculus", "why": "studied"} in paths["excluded"]
    assert cli.main(["prerequisites", "analyze", SAMPLE, "--paths", "--studied", "Calculus"]) == 0
    out = capsys.readouterr().out
    assert "learning paths (foundations first):" in out and "skipped: Calculus (studied)" in out
    shown = [line.split(".", 1)[1].split(" (~")[0].strip() for line in out.splitlines() if line.startswith("    ") and ". " in line[:8]]
    assert shown == [c["concept"] for c in paths["combined"]]


def test_the_web_page_renders_the_paths_from_the_server_report():
    page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    for fragment in ('id="paths"', "function renderPaths()", "report.study_paths", "refreshPaths()", "body.study_paths", "(through other prerequisites)", "safeUrl(r.url)"):
        assert fragment in page, fragment
    assert "innerHTML" not in page
