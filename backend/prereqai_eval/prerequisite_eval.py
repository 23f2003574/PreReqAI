"""Precision and recall of the prerequisites PreReqAI recommends for the six real papers, against prerequisite_annotations.json (AI-written, PROVISIONAL, unreviewed).

A paper's predicted set is the names in `paper.prerequisites`; the annotated set is what a reader needs to follow it. Per paper and micro-averaged: precision, recall, the false positives (recommended but not annotated)
and the false negatives (annotated but not recommended). These are scores against one AI annotator's judgement of six papers: they guard against regressions and show where the table disagrees, they do not
validate the prerequisite table."""
import json
from pathlib import Path

ANNOTATIONS = Path(__file__).resolve().parent / "prerequisite_annotations.json"


def load(path=ANNOTATIONS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "prereqai-prerequisite-annotations":
        raise ValueError(f"{path} is not a prerequisite annotation file")
    return data


def evaluate(papers, data=None):
    """{"papers": {id: {precision, recall, tp, fp, fn, false_positives, false_negatives}}, "precision", "recall", "tp", "fp", "fn", "status"} for `papers` ({id: analysed Paper})."""
    data = data or load()
    rows, tp, fp, fn = {}, 0, 0, 0
    for paper_id, wanted in data["papers"].items():
        if paper_id not in papers:
            continue
        got, want = {p.concept for p in papers[paper_id].prerequisites}, set(wanted)
        row = {"tp": len(got & want), "fp": len(got - want), "fn": len(want - got), "false_positives": sorted(got - want), "false_negatives": sorted(want - got)}
        row["precision"] = round(row["tp"] / len(got), 3) if got else 1.0
        row["recall"] = round(row["tp"] / len(want), 3) if want else 1.0
        rows[paper_id] = row
        tp, fp, fn = tp + row["tp"], fp + row["fp"], fn + row["fn"]
    return {"papers": rows, "tp": tp, "fp": fp, "fn": fn, "precision": round(tp / (tp + fp), 3) if tp + fp else 1.0, "recall": round(tp / (tp + fn), 3) if tp + fn else 1.0, "status": data["status"]}
