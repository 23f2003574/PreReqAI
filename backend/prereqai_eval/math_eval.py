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


REAL_FIXTURE = Path(__file__).with_name("fixtures") / "real_equations.json"


def _flat(text):
    return " ".join(str(text).split())


def load_real(path=REAL_FIXTURE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "prereqai-real-equations":
        raise ValueError(f"{path} is not a real-equations fixture")
    return data


def evaluate_real(papers, path=REAL_FIXTURE, subtopics_of=None):
    """The mathematical stage on equations EXTRACTED FROM REAL PDFs (`papers`: {paper id: analysed Paper}), against `fixtures/real_equations.json` (AI-annotated, provisional, unreviewed: see its provenance).
    Extraction: of the extracted items the fixture knows, `extraction_precision` is the share that are display equations (the rest are chart legends, table cells, code or prose reported as equations) and
    `extraction_recall` the share of the annotated equations still extracted; items the fixture has never seen are counted in `unannotated` (the extraction changed) and never scored. Rules: precision and
    recall over (equation, subtopic) pairs of the annotated equations, per subtopic, with every false positive and negative named. Equations whose Sigma or fraction bar the text layer lost are labelled with
    what a reader needs, so those misses count against the rules."""
    from backend.parsing import math_subtopics

    find = subtopics_of or math_subtopics.subtopics_of
    data = load_real(path)
    items = [i for i in data["items"] if i["paper"] in papers]
    known = {(i["paper"], _flat(i["expression"])): i for i in items}
    seen, unannotated, false_extractions, true_extracted = set(), [], [], 0
    for paper_id, paper in sorted(papers.items()):
        for equation in getattr(paper, "equations", []) or []:
            key = (paper_id, _flat(equation.expression))
            item = known.get(key)
            if item is None:
                unannotated.append(f"{paper_id}: {key[1][:80]}")
            elif key not in seen:
                seen.add(key)
                if item["is_equation"]:
                    true_extracted += 1
                else:
                    false_extractions.append(item["id"])
    annotated = [i for i in items if i["is_equation"]]
    per, fps, fns = {}, [], []
    for row in annotated:
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
    return {"precision": share(tp, tp + fp), "recall": share(tp, tp + fn), "tp": tp, "fp": fp, "fn": fn, "annotated_equations": len(annotated), "papers": sorted({i["paper"] for i in items}),
            "extraction_precision": share(true_extracted, true_extracted + len(false_extractions)), "extraction_recall": share(true_extracted, len(annotated)), "false_extractions": false_extractions,
            "unannotated": unannotated, "per_subtopic": dict(sorted(per.items())), "false_positives": fps, "false_negatives": fns, "status": data["status"], "provenance": data["provenance"]}
