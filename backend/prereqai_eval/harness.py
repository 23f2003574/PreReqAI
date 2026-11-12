"""Reproducible evaluation of concept and prerequisite detection against hand-labelled paper-text fixtures.

Runs the real detectors (RuleBasedConceptDetector, PrerequisiteDetector, MissingPrerequisiteAnalyzer) on each fixture's text,
offline and deterministically, and compares the result with the annotations. Detection rules are never tuned to the fixtures."""
import json
from pathlib import Path

from backend.concepts import ConceptRegistry, RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.prerequisites.missing_prerequisite_analyzer import MissingPrerequisiteAnalyzer
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

DEFAULT_FIXTURES = Path(__file__).with_name("fixtures") / "papers.json"
_LIST_FIELDS = ("expected_concepts", "expected_prerequisites", "out_of_registry")


class AnnotationError(ValueError):
    """The annotation file is malformed; the message says which fixture and field."""


def _subjects():
    rules = PrerequisiteDetector.PREREQUISITE_RULES
    return {c.name for c in ConceptRegistry().all()} | {p for targets in rules.values() for p in targets}


def load_fixtures(path=DEFAULT_FIXTURES):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AnnotationError(f"cannot read annotations {path}: {error}") from error
    fixtures = data.get("fixtures") if isinstance(data, dict) else None
    if not isinstance(fixtures, list) or not fixtures:
        raise AnnotationError("annotations must be an object with a non-empty 'fixtures' list")
    registry = {c.name for c in ConceptRegistry().all()}
    subjects, seen = _subjects(), set()
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            raise AnnotationError(f"fixture #{index} is not an object")
        name = fixture.get("id")
        if not isinstance(name, str) or not name.strip():
            raise AnnotationError(f"fixture #{index} has no string 'id'")
        if name in seen:
            raise AnnotationError(f"duplicate fixture id '{name}'")
        seen.add(name)
        for field in ("title", "source", "text"):
            if not isinstance(fixture.get(field), str) or not fixture[field].strip():
                raise AnnotationError(f"fixture '{name}': '{field}' must be a non-empty string")
        for field in _LIST_FIELDS:
            values = fixture.get(field)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values) or len(set(values)) != len(values):
                raise AnnotationError(f"fixture '{name}': '{field}' must be a list of unique strings")
        unknown = [c for c in fixture["expected_concepts"] if c not in registry]
        if unknown:
            raise AnnotationError(f"fixture '{name}': expected_concepts not in the registry: {unknown} (list them under out_of_registry)")
        unknown = [p for p in fixture["expected_prerequisites"] if p not in subjects]
        if unknown:
            raise AnnotationError(f"fixture '{name}': expected_prerequisites are not known subjects: {unknown}")
    return fixtures


def scores(expected, found):
    """Precision, recall and F1 of two sets. Nothing expected and nothing found is a perfect 1.0 (a correct empty answer);
    otherwise an empty side scores 0.0 instead of dividing by zero."""
    expected, found = set(expected), set(found)
    hit = len(expected & found)
    if not expected and not found:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    precision = hit / len(found) if found else 0.0
    recall = hit / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "tp": hit, "fp": len(found - expected), "fn": len(expected - found)}


def _detect(text):
    paper = Paper(source_path="fixture", metadata=None)
    paper.paragraphs = [Paragraph(paragraph_id=i, section_title="Body", content=chunk.strip())
                        for i, chunk in enumerate(text.split("\n\n"), start=1) if chunk.strip()]
    RuleBasedConceptDetector().detect(paper)
    PrerequisiteDetector().detect(paper)
    MissingPrerequisiteAnalyzer().analyze(paper)
    concepts = {c.name for c in paper.concepts}
    needed = {m.concept for m in paper.missing_prerequisites if not m.satisfied}
    return concepts, needed


def evaluate(path=DEFAULT_FIXTURES):
    """{'fixtures': [...per fixture...], 'concepts': micro scores, 'prerequisites': micro scores}; sorted lists, no clocks."""
    results, totals = [], {"concepts": [0, 0, 0], "prerequisites": [0, 0, 0]}
    for fixture in load_fixtures(path):
        concepts, needed = _detect(fixture["text"])
        row = {"id": fixture["id"], "title": fixture["title"]}
        for key, expected, found in (("concepts", fixture["expected_concepts"], concepts),
                                     ("prerequisites", fixture["expected_prerequisites"], needed)):
            result = scores(expected, found)
            result["missed"], result["spurious"] = sorted(set(expected) - found), sorted(found - set(expected))
            row[key] = result
            for position, field in enumerate(("tp", "fp", "fn")):
                totals[key][position] += result[field]
        row["out_of_registry"] = sorted(fixture["out_of_registry"])  # real topics the registry cannot detect; not scored
        results.append(row)
    summary = {}
    for key, (tp, fp, fn) in totals.items():
        precision, recall = (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        summary[key] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn}
    return {"fixtures": results, **summary}


def render(report):
    lines = []
    for row in report["fixtures"]:
        for key in ("concepts", "prerequisites"):
            r = row[key]
            lines.append(f"{row['id']:<13}{key:<14}P={r['precision']:.2f} R={r['recall']:.2f} F1={r['f1']:.2f}"
                         + (f"  missed={r['missed']}" if r["missed"] else "") + (f"  spurious={r['spurious']}" if r["spurious"] else ""))
    for key in ("concepts", "prerequisites"):
        r = report[key]
        lines.append(f"{'MICRO':<13}{key:<14}P={r['precision']:.2f} R={r['recall']:.2f} F1={r['f1']:.2f} (tp={r['tp']} fp={r['fp']} fn={r['fn']})")
    return "\n".join(lines)
