"""The built-in prerequisite rules form a clean graph: no concept needs itself and no chain loops back on itself."""
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

RULES = PrerequisiteDetector.PREREQUISITE_RULES


def _cycle_from(start, path=()):
    if start in path:
        return [*path[path.index(start):], start]
    for target in RULES.get(start, []):
        found = _cycle_from(target, (*path, start))
        if found:
            return found
    return None


def test_no_rule_lists_itself_or_repeats_a_prerequisite():
    for concept, targets in RULES.items():
        assert concept not in targets, f"{concept!r} lists itself as a prerequisite"
        assert len(targets) == len(set(targets)), f"{concept!r} repeats a prerequisite: {targets}"


def test_no_prerequisite_chain_is_cyclic():
    for concept in RULES:
        cycle = _cycle_from(concept)
        assert cycle is None, "cyclic prerequisite chain: " + " -> ".join(cycle)


def test_a_valid_chain_resolves_transitively_in_order():
    assert _cycle_from("Transformer") is None and "Attention" in RULES["Transformer"]
