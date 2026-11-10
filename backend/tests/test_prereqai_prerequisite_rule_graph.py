"""Structural validation of PrerequisiteDetector.PREREQUISITE_RULES (concept -> list of prerequisites)."""
import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai

RULES = PrerequisiteDetector.PREREQUISITE_RULES
REGISTRY = {c.name for c in ConceptRegistry().all()}
# Foundational subjects: valid prerequisites (and, for Information Theory, a rule key) without being detectable registry concepts.
BASE_SUBJECTS = {"Linear Algebra", "Probability", "Calculus", "Information Theory", "Graphs", "Neural Networks"}
KNOWN = REGISTRY | BASE_SUBJECTS


def _cycle(rules):
    """Return one dependency cycle as a list of names, or None (iterative DFS over concept -> prerequisites)."""
    state = {}
    for start in rules:
        if state.get(start):
            continue
        stack = [(start, iter(rules.get(start, ())))]
        path = [start]
        state[start] = 1
        while stack:
            node, children = stack[-1]
            for child in children:
                if state.get(child) == 1:
                    return path[path.index(child):] + [child]
                if not state.get(child):
                    state[child] = 1
                    path.append(child)
                    stack.append((child, iter(rules.get(child, ()))))
                    break
            else:
                state[node] = 2
                path.pop()
                stack.pop()
    return None


def test_rule_keys_and_prerequisites_are_known_concepts():
    unknown = {name for key, targets in RULES.items() for name in (key, *targets)} - KNOWN
    assert not unknown, f"rules reference concepts missing from the registry: {sorted(unknown)}"


def test_base_subjects_exceptions_are_not_stale():
    assert not (BASE_SUBJECTS & REGISTRY), "a base subject is now a registry concept; drop it from BASE_SUBJECTS"


def test_no_self_referential_rule():
    assert [k for k, targets in RULES.items() if k in targets] == []


def test_no_duplicate_prerequisites_within_a_rule():
    assert [k for k, targets in RULES.items() if len(set(targets)) != len(targets)] == []


def test_prerequisite_graph_is_acyclic():
    assert _cycle(RULES) is None


def test_cycle_checker_detects_cycles():
    assert _cycle({"A": ["B"], "B": ["C"], "C": ["A"]}) == ["A", "B", "C", "A"]
    assert _cycle({"A": ["A"]}) == ["A", "A"]
    assert _cycle({"A": ["B", "C"], "B": ["C"]}) is None
