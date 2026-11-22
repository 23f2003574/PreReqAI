"""Precision and recall of the mathematical-subtopic rules (backend/parsing/math_subtopics.py) on labelled equations.

`fixtures/math_equations.json` lists equations written in the style of a PDF text layer with the subtopics a reader needs for each (empty for equations that need none: prose arithmetic, plain
sums of symbols). Its `provenance` says honestly where it comes from: AI-written and unreviewed, NOT extracted from real PDFs. Real-paper equations cannot be annotated reliably without running the
PDF text extraction, whose output (lost subscripts, fractions flattened into one line, symbols replaced by glyph names) decides what a rule can see; until a human annotates equations that came out
of the real extraction, `real_papers` below stays "not annotated" and nothing is claimed about them. Offline and deterministic. `evaluate` returns micro precision and recall over (equation, subtopic)
pairs, the same per subtopic, and every false positive and false negative by name; the regression gate holds floors on them (thresholds.json, "math_subtopics")."""
import json
from pathlib import Path

FIXTURE = Path(__file__).with_name("fixtures") / "math_equations.json"


def load(path=FIXTURE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "prereqai-math-equations":
        raise ValueError(f"{path} is not a math equations fixture")
    return data


def evaluate(path=FIXTURE, subtopics_of=None):
    """{"precision", "recall", "tp", "fp", "fn", "equations", "per_subtopic": {name: {tp, fp, fn, precision, recall}}, "false_positives": [...], "false_negatives": [...], "provenance",
    "status", "real_papers": "not annotated"}. `subtopics_of` replaces the rules (default: math_subtopics.subtopics_of), so a degraded rule set can be scored."""
    from backend.parsing import math_subtopics

    find = subtopics_of or math_subtopics.subtopics_of
    data, per, fps, fns = load(path), {}, [], []
    for row in data["equations"]:
        got, want = {topic for topic, _, _, _ in find(row["expression"])}, set(row["expected"])
        for topic in got | want:
            entry = per.setdefault(topic, {"tp": 0, "fp": 0, "fn": 0})
            if topic in got and topic in want:
                entry["tp"] += 1
            elif topic in got:
                entry["fp"] += 1
                fps.append(f"{row['id']}: {topic}")
            else:
                entry["fn"] += 1
                fns.append(f"{row['id']}: {topic}")
    tp, fp, fn = (sum(e[k] for e in per.values()) for k in ("tp", "fp", "fn"))
    share = lambda a, b: a / b if b else 1.0
    for entry in per.values():
        entry["precision"], entry["recall"] = round(share(entry["tp"], entry["tp"] + entry["fp"]), 3), round(share(entry["tp"], entry["tp"] + entry["fn"]), 3)
    return {"precision": share(tp, tp + fp), "recall": share(tp, tp + fn), "tp": tp, "fp": fp, "fn": fn, "equations": len(data["equations"]), "per_subtopic": dict(sorted(per.items())),
            "false_positives": fps, "false_negatives": fns, "provenance": data["provenance"], "status": data["status"], "real_papers": "not annotated"}
