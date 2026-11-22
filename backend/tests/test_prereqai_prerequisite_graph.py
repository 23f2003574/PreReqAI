"""The prerequisite graph is versioned data with per-edge provenance, validated, covered and equal to what the detector has always used."""
import json
from copy import deepcopy

import pytest

from backend.concepts.ml_expansion import RULES as EXPANSION
from backend.prerequisites import prerequisite_graph as graph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def sound(extra=()):
    return [{"concept": "A", "needs": ["Calculus"], "kind": "curated", "source": graph.MAINTAINERS, "rationale": "r"}, *extra]


def test_the_detector_uses_the_graph_and_every_edge_has_a_kind_source_and_rationale():
    rules = graph.rules()
    assert PrerequisiteDetector.PREREQUISITE_RULES == rules and set(EXPANSION) <= set(rules) and len(rules) >= 100
    for entry in graph.load():
        assert entry["kind"] in graph.KINDS and entry["source"] == graph.MAINTAINERS or entry["source"].startswith(graph.MAINTAINERS)
        assert entry["rationale"]
    assert graph.provenance("Transformer", "Attention")["source"] == graph.MAINTAINERS and graph.provenance("Transformer", "Calculus") is None
    assert graph.edges_into(["Transformer", "Softmax"], "Attention")[0]["needed_by"] == "Transformer"


def test_the_shipped_graph_validates_and_covers_the_registry():
    assert graph.validate(graph.entries()) == []
    covered = graph.coverage()
    assert covered["ratio"] >= 0.98 and covered["without_rules"] == [name for name in covered["without_rules"]]


def test_unknown_targets_cycles_duplicates_and_missing_provenance_are_refused():
    assert graph.validate(sound()) == []
    assert any("not a known concept" in p for p in graph.validate(sound([{"concept": "B", "needs": ["Nonexistent Thing"], "kind": "curated", "source": "s", "rationale": "r"}])))
    cyc = sound([{"concept": "Calculus", "needs": ["A"], "kind": "curated", "source": "s", "rationale": "r"}])
    assert any("cycle" in p for p in graph.validate(cyc))
    assert any("more than one rule" in p for p in graph.validate(sound(sound())))
    assert any("source and a rationale" in p for p in graph.validate([{"concept": "A", "needs": ["Calculus"], "kind": "curated"}]))
    assert any("depends on itself" in p for p in graph.validate([{"concept": "Calculus", "needs": ["Calculus"], "kind": "curated", "source": "s", "rationale": "r"}]))
    assert any("no study hours" in p for p in graph.validate(sound(), has_hours=lambda name: False))


def test_a_broken_file_is_an_error_naming_the_problem(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps({"format": "other"}))
    with pytest.raises(graph.GraphError):
        graph.rules(path)
    data = json.loads(graph.DATA.read_text(encoding="utf-8"))
    data["rules"].append(deepcopy(data["rules"][0]))
    path.write_text(json.dumps(data))
    with pytest.raises(graph.GraphError) as info:
        graph.rules(path)
    assert any("more than one rule" in p for p in info.value.problems)


def test_uncovered_concepts_are_reported_by_name():
    covered = graph.coverage(["Transformer", "Totally New Concept"])
    assert covered["without_rules"] == ["Totally New Concept"] and covered["ratio"] == 0.5
