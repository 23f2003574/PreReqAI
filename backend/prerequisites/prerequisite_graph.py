"""The prerequisite rules as an auditable, versioned graph: every edge with its kind, source and rationale, validated, with a coverage measure.

The core rules are data (`prerequisite_graph.json`, format "prereqai-prerequisite-graph"); the rules of the modern ML concepts sit with their explanations in `concepts/ml_expansion.py` and are
merged here. Every edge is "curated": chosen by the maintainers, whose source is stated as "curated by maintainers" because no academic citation is recorded for it (none is invented). `rules()`
returns {concept: [prerequisites]} in the order the detector has always used. `validate` reports duplicate concepts, empty or duplicated prerequisites, unknown targets (not a registry concept or a
foundational subject), self-dependencies, cycles and targets the planner has no study hours for. `coverage` says which registry concepts have no rule at all: their prerequisites are unknown, not absent."""
import json
from pathlib import Path

DATA = Path(__file__).with_name("prerequisite_graph.json")
FORMAT, SCHEMA_VERSION = "prereqai-prerequisite-graph", 1
KINDS = ("curated", "inferred")
# Foundational subjects: valid prerequisites without being detectable registry concepts.
BASE_SUBJECTS = frozenset({"Linear Algebra", "Probability", "Calculus", "Information Theory", "Graphs", "Neural Networks", "Optimization", "Statistics", "Stochastic Processes"})
MAINTAINERS = "curated by maintainers"
_cache = {}


class GraphError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GraphError([f"cannot read the prerequisite graph {path}: {error}"]) from None
    if data.get("format") != FORMAT or data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("rules"), list):
        raise GraphError([f"{path} is not a version {SCHEMA_VERSION} {FORMAT} file"])
    return data["rules"]


def entries(path=None, include_expansion=True):
    """[{concept, needs, kind, source, rationale}] in rule order: the core file, then the modern ML concepts."""
    found = [dict(rule) for rule in _read(path or DATA)]
    if include_expansion:
        from backend.concepts.ml_expansion import RULES as EXPANSION

        found += [{"concept": name, "needs": list(needs), "kind": "curated", "source": MAINTAINERS + " (concepts/ml_expansion.py)",
                   "rationale": f"Maintainers list {', '.join(needs)} as background needed to follow {name}."} for name, needs in EXPANSION.items()]
    return found


def _cycle(rules):
    state = {}

    def visit(node, path):
        state[node] = 1
        for child in rules.get(node, ()):
            if state.get(child) == 1:
                return path[path.index(child):] + [child] if child in path else [node, child]
            if not state.get(child):
                found = visit(child, path + [child])
                if found:
                    return found
        state[node] = 2
        return None

    for start in rules:
        if not state.get(start):
            found = visit(start, [start])
            if found:
                return found
    return None


def validate(found, known=None, has_hours=None):
    """The list of problems of `found` (entries): empty when the graph is sound. `known`: names allowed as prerequisites (default: the registry and the foundational subjects); `has_hours(name)`:
    whether the planner has study hours for a prerequisite (default: the curated resource library)."""
    if known is None:
        from backend.concepts.concept_registry import ConceptRegistry

        known = {c.name for c in ConceptRegistry().all()} | BASE_SUBJECTS
    if has_hours is None:
        from backend.resources.learning_resource_recommender import LearningResourceRecommender

        has_hours = lambda name: LearningResourceRecommender.for_concept(name) is not None
    problems, seen, rules = [], set(), {}
    for rule in found:
        concept, needs = rule.get("concept"), rule.get("needs")
        if not isinstance(concept, str) or not concept or not isinstance(needs, list) or not needs or not all(isinstance(n, str) for n in needs):
            problems.append(f"a rule needs a concept name and a non-empty list of prerequisite names: {rule!r}")
            continue
        if concept in seen:
            problems.append(f"{concept}: more than one rule")
        seen.add(concept)
        if rule.get("kind") not in KINDS or not rule.get("source") or not rule.get("rationale"):
            problems.append(f"{concept}: a rule needs a kind ({', '.join(KINDS)}), a source and a rationale")
        if len(set(needs)) != len(needs):
            problems.append(f"{concept}: a prerequisite is listed twice")
        for need in needs:
            if need == concept:
                problems.append(f"{concept}: depends on itself")
            elif need not in known:
                problems.append(f"{concept}: the prerequisite {need!r} is not a known concept or subject")
            elif not has_hours(need):
                problems.append(f"{concept}: the prerequisite {need!r} has no study hours in the planner")
        rules[concept] = needs
    cycle = _cycle(rules)
    if cycle:
        problems.append("a dependency cycle: " + " -> ".join(cycle))
    return problems


def load(path=None):
    """The validated entries of the graph; GraphError listing every problem."""
    key = str(path or DATA)
    if key not in _cache:
        found = entries(path)
        problems = validate(found)
        if problems:
            raise GraphError(problems)
        _cache[key] = found
    return _cache[key]


def rules(path=None):
    """{concept: [prerequisites]} as the detector uses it (a new dict each call)."""
    return {entry["concept"]: list(entry["needs"]) for entry in load(path)}


def provenance(concept, need):
    """{kind, source, rationale} of the edge concept -> need, or None when there is no such edge."""
    for entry in load():
        if entry["concept"] == concept and need in entry["needs"]:
            return {"kind": entry["kind"], "source": entry["source"], "rationale": entry["rationale"]}
    return None


def edges_into(paper_concepts, need):
    """[{needed_by, kind, source, rationale}] for the paper's concepts whose rule lists `need`."""
    wanted, found = set(paper_concepts), []
    for entry in load():
        if entry["concept"] in wanted and need in entry["needs"]:
            found.append({"needed_by": entry["concept"], "kind": entry["kind"], "source": entry["source"], "rationale": entry["rationale"]})
    return found


def coverage(names=None):
    """{"concepts", "with_rules", "ratio", "without_rules": [...]}: how many registry concepts (or `names`) have a prerequisite rule. A concept without one has UNKNOWN prerequisites, not none."""
    if names is None:
        from backend.concepts.concept_registry import ConceptRegistry

        names = [c.name for c in ConceptRegistry().all()]
    have = {entry["concept"] for entry in load()}
    without = sorted(name for name in names if name not in have)
    return {"concepts": len(names), "with_rules": len(names) - len(without), "ratio": round((len(names) - len(without)) / len(names), 3) if names else 1.0, "without_rules": without}
