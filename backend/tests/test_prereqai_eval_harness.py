"""The detection evaluation harness: scoring, deterministic runs, malformed annotations, empty detections."""
import copy
import json

import pytest

from backend.prereqai_eval import AnnotationError, evaluate, load_fixtures
from backend.prereqai_eval.__main__ import main
from backend.prereqai_eval.harness import DEFAULT_FIXTURES, scores

pytestmark = pytest.mark.prereqai

GOOD = {"id": "x", "title": "T", "source": "s", "text": "The Transformer uses attention.", "expected_concepts": ["Transformer"],
        "expected_prerequisites": ["Linear Algebra"], "out_of_registry": []}


def _write(tmp_path, *fixtures):
    path = tmp_path / "a.json"
    path.write_text(json.dumps({"fixtures": list(fixtures)}), encoding="utf-8")
    return path


def test_scores_precision_recall_f1():
    assert scores({"a", "b"}, {"a", "c"}) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1, "fp": 1, "fn": 1}


def test_scores_handle_empty_sides_without_dividing_by_zero():
    assert scores(set(), set())["f1"] == 1.0  # correctly found nothing
    assert scores({"a"}, set()) == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 1}
    assert scores(set(), {"a"})["precision"] == 0.0


def test_bundled_fixtures_are_valid_and_the_run_is_deterministic():
    assert len(load_fixtures(DEFAULT_FIXTURES)) >= 6
    first = evaluate()
    assert first == evaluate()
    for key in ("concepts", "prerequisites"):
        assert all(0.0 <= first[key][m] <= 1.0 for m in ("precision", "recall", "f1"))


def test_out_of_scope_text_detects_nothing_and_scores_as_a_correct_empty_answer():
    row = next(r for r in evaluate()["fixtures"] if r["id"] == "out_of_scope")
    assert row["concepts"]["f1"] == 1.0 and row["concepts"]["spurious"] == [] and row["prerequisites"]["spurious"] == []


def test_empty_detection_on_a_labelled_fixture_is_zero_recall(tmp_path):
    blank = dict(GOOD, text="Nothing relevant is written here at all.")
    row = evaluate(_write(tmp_path, blank))["fixtures"][0]
    assert row["concepts"]["recall"] == 0.0 and row["concepts"]["missed"] == ["Transformer"] and row["concepts"]["f1"] == 0.0


def _bad(**change):
    fixture = copy.deepcopy(GOOD)
    fixture.update(change)
    return fixture


@pytest.mark.parametrize("fixture, message", [
    (_bad(id=""), "'id'"),
    (_bad(text="  "), "'text'"),
    (_bad(expected_concepts="Transformer"), "expected_concepts"),
    (_bad(expected_concepts=["Transformer", "Transformer"]), "unique"),
    (_bad(expected_concepts=["Quantum Gravity"]), "not in the registry"),
    (_bad(expected_prerequisites=["Alchemy"]), "not known subjects"),
    (_bad(out_of_registry=None), "out_of_registry"),
])
def test_malformed_annotations_are_rejected_with_the_field_named(tmp_path, fixture, message):
    with pytest.raises(AnnotationError, match=message):
        load_fixtures(_write(tmp_path, fixture))


def test_duplicate_ids_a_non_object_and_unreadable_files_are_rejected(tmp_path):
    with pytest.raises(AnnotationError, match="duplicate"):
        load_fixtures(_write(tmp_path, GOOD, GOOD))
    with pytest.raises(AnnotationError, match="not an object"):
        load_fixtures(_write(tmp_path, "oops"))
    broken = tmp_path / "b.json"
    broken.write_text("{not json", encoding="utf-8")
    for path in (broken, tmp_path / "missing.json"):
        with pytest.raises(AnnotationError, match="cannot read"):
            load_fixtures(path)
    empty = tmp_path / "e.json"
    empty.write_text('{"fixtures": []}', encoding="utf-8")
    with pytest.raises(AnnotationError, match="non-empty"):
        load_fixtures(empty)


def test_command_prints_scores_json_and_reports_bad_files(tmp_path, capsys):
    assert main([]) == 0 and "MICRO" in capsys.readouterr().out
    assert main(["--json"]) == 0 and "prerequisites" in json.loads(capsys.readouterr().out)
    assert main(["--fixtures", str(tmp_path / "nope.json")]) == 2 and "error:" in capsys.readouterr().err
