import json
from types import SimpleNamespace

import pytest

from backend.prereqai_eval import gate, prerequisite_eval

pytestmark = pytest.mark.prereqai


def _papers(**found):
    return {pid: SimpleNamespace(prerequisites=[SimpleNamespace(concept=c) for c in names]) for pid, names in found.items()}


def test_the_annotation_file_is_marked_provisional_and_names_six_papers():
    data = prerequisite_eval.load()
    assert data["status"] == "provisional" and "AI assistant" in data["provenance"] and len(data["papers"]) == 6


def test_annotated_names_are_known_registry_concepts_or_subjects():
    from backend.learner_profile import vocabulary

    known = set(vocabulary().values())
    unknown = {name for names in prerequisite_eval.load()["papers"].values() for name in names} - known
    assert not unknown, unknown


def test_precision_recall_and_the_named_errors():
    data = {"status": "provisional", "papers": {"a": ["X", "Y", "Z"], "b": ["X"]}}
    report = prerequisite_eval.evaluate(_papers(a=["X", "Q"], b=["X"]), data)
    assert report["papers"]["a"] == {"tp": 1, "fp": 1, "fn": 2, "false_positives": ["Q"], "false_negatives": ["Y", "Z"], "precision": 0.5, "recall": 0.333}
    assert (report["tp"], report["fp"], report["fn"]) == (2, 1, 2) and report["precision"] == 0.667 and report["recall"] == 0.5


def test_a_paper_without_annotation_is_left_out_and_an_empty_prediction_scores_zero_recall():
    report = prerequisite_eval.evaluate(_papers(a=[], other=["X"]), {"status": "provisional", "papers": {"a": ["X"]}})
    assert list(report["papers"]) == ["a"] and report["recall"] == 0.0


def test_the_gate_fails_below_a_floor_and_names_the_errors():
    checks = []
    gate.real_prerequisite_checks(checks, {"precision": 0.9, "recall": 0.9}, papers=_papers(dpo=["Statistics"]))
    assert [c["passed"] for c in checks] == [False, False] and "dpo" in checks[0]["detail"]
