"""The regression gate: `python -m backend.prereqai_eval --gate` scores the pipeline on gold data that ships with the repository and fails (exit code 1) when a score falls below its floor in
thresholds.json. Offline and deterministic (no network, no model, no randomness): the same code gives the same numbers.

Four groups, reported apart:
* text_fixtures: the labelled text fixtures of the evaluation harness (concept and prerequisite scores);
* synthetic_pdf: generated academic PDFs with known headings, roles, concepts and covered prerequisites (written for this repository, so a score on them is evidence about the pipeline's logic,
  not about real papers), run through the whole pipeline;
* synthetic_evidence: on the same PDFs, the evidence passages (backend/evidence.py): every annotated concept has one, every one is an exact quotation of the page it cites, none is chart residue;
* real_papers_provisional: the three CC BY papers of the real-paper benchmark. Their annotations were approved by an AI, not a human, so these floors are PROVISIONAL: they guard against
  regressions on real text but are not validated ground truth, and nothing here counts an annotation that is pending or approved only by an AI as human-reviewed."""
import json
import re
import tempfile
from pathlib import Path

THRESHOLDS = Path(__file__).with_name("thresholds.json")


def load_thresholds(path=THRESHOLDS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "prereqai-gate-thresholds":
        raise ValueError(f"{path} is not a gate thresholds file")
    return data


def _check(checks, group, metric, value, floor, detail=""):
    checks.append({"group": group, "metric": metric, "value": round(value, 3), "threshold": floor, "passed": value >= floor, "detail": detail})


def evidence_scores(fixtures=None):
    """Evidence passage quality on the generated PDFs, where the truth is known: the share of annotated concepts with at least one passage, and the share of passages that are exact
    quotations of the page they cite, free of residue, mention their concept and carry a page."""
    from backend.concepts.concept_registry import ConceptRegistry
    from backend.evidence import _pattern, build_evidence, residue_share
    from backend.pipeline import ResearchPaperPipeline

    from .pdf_eval import FIXTURES, write_fixture_pdfs

    registry = {c.name: c for c in ConceptRegistry().all()}
    wanted = found = passages = exact = clean = mentions = paged = 0
    missing = []
    with tempfile.TemporaryDirectory() as directory:
        for fixture_id, path in write_fixture_pdfs(directory, fixtures).items():
            fixture = next(f for f in (fixtures or FIXTURES) if f["id"] == fixture_id)
            paper = ResearchPaperPipeline().run(str(path)).paper
            pages = {p.page_number: p.text for p in paper.pages}
            evidence = build_evidence(paper)
            for concept in fixture["concepts"]:
                wanted += 1
                if evidence.get(concept):
                    found += 1
                else:
                    missing.append(f"{fixture_id}: {concept}")
                for passage in evidence.get(concept, []):
                    passages += 1
                    exact += passage["sentence"] in pages.get(passage["page_number"], "")
                    clean += residue_share(passage["sentence"]) <= 0.35
                    mentions += bool(_pattern(registry[concept]).search(passage["sentence"]))
                    paged += passage["page_number"] is not None
    share = lambda part, whole: part / whole if whole else 1.0
    return {"concept_coverage": share(found, wanted), "exact_quotation": share(exact, passages), "residue_free": share(clean, passages), "mentions_concept": share(mentions, passages),
            "page_known": share(paged, passages), "missing": missing, "passages": passages}


def run_gate(thresholds=None, benchmark_manifest=None):
    """{"passed", "checks": [...], "real_papers": {...}} for the thresholds (default: thresholds.json). Never raises for a failed score: a failure is a failed check."""
    from . import benchmark
    from .harness import DEFAULT_FIXTURES, evaluate
    from .pdf_eval import evaluate_pdf

    floors = thresholds or load_thresholds()
    checks = []
    text = evaluate(str(DEFAULT_FIXTURES))
    group = floors["text_fixtures"]
    _check(checks, "text_fixtures", "concepts_precision", text["concepts"]["precision"], group["concepts_precision"], f"fp={text['concepts']['fp']}")
    _check(checks, "text_fixtures", "concepts_recall", text["concepts"]["recall"], group["concepts_recall"], f"fn={text['concepts']['fn']}")
    _check(checks, "text_fixtures", "prerequisites_recall", text["prerequisites"]["recall"], group["prerequisites_recall"], f"fn={text['prerequisites']['fn']}")
    _check(checks, "text_fixtures", "prerequisites_precision", text["prerequisites"]["precision"], group["prerequisites_precision"], f"fp={text['prerequisites']['fp']}")
    pdf = evaluate_pdf()
    group = floors["synthetic_pdf"]
    _check(checks, "synthetic_pdf", "headings_f1", pdf["headings"]["f1"], group["headings_f1"], "; ".join(f"{r['id']}: missed {r['headings'].get('missed', [])} spurious {r['headings'].get('spurious', [])}" for r in pdf["fixtures"] if r["ok"] and (r["headings"].get("missed") or r["headings"].get("spurious"))))
    _check(checks, "synthetic_pdf", "concepts_precision", pdf["concepts"]["precision"], group["concepts_precision"])
    _check(checks, "synthetic_pdf", "concepts_recall", pdf["concepts"]["recall"], group["concepts_recall"])
    _check(checks, "synthetic_pdf", "roles_accuracy", pdf["roles"]["accuracy"], group["roles_accuracy"])
    _check(checks, "synthetic_pdf", "coverage_recall", pdf["coverage"]["recall"], group["coverage_recall"])
    _check(checks, "synthetic_pdf", "coverage_f1", pdf["coverage"]["f1"], group["coverage_f1"])
    _check(checks, "synthetic_pdf", "pipeline_success", pdf["pipeline"]["succeeded"] / max(1, pdf["pipeline"]["total"]), group["pipeline_success"])
    evidence = evidence_scores()
    group = floors["synthetic_evidence"]
    for metric in ("concept_coverage", "exact_quotation", "residue_free", "mentions_concept", "page_known"):
        _check(checks, "synthetic_evidence", metric, evidence[metric], group[metric], f"missing: {evidence['missing']}" if metric == "concept_coverage" and evidence["missing"] else "")
    real = benchmark.evaluate_benchmark(benchmark_manifest or benchmark.DEFAULT_MANIFEST)
    group = floors["real_papers_provisional"]
    _check(checks, "real_papers_provisional", "evaluated_papers", real["counts"]["evaluated"], group["evaluated_papers"], "a paper drops out when its licence, PDF hash or approved annotation is lost")
    if real["counts"]["evaluated"]:
        worst = lambda key, field: "; ".join(f"{r['id']}: {field} {r[key][field]}" for r in real["papers"] if r["ok"] and r[key][field])
        _check(checks, "real_papers_provisional", "headings_f1", real["headings"]["f1"], group["headings_f1"], worst("headings", "missed") + (" | spurious " + worst("headings", "spurious") if worst("headings", "spurious") else ""))
        _check(checks, "real_papers_provisional", "concepts_precision", real["concepts"]["precision"], group["concepts_precision"], "false positives: " + worst("concepts", "spurious"))
        _check(checks, "real_papers_provisional", "concepts_recall", real["concepts"]["recall"], group["concepts_recall"], "false negatives: " + worst("concepts", "missed"))
        _check(checks, "real_papers_provisional", "roles_accuracy", real["roles"]["accuracy"], group["roles_accuracy"], "wrong roles: " + worst("roles", "wrong"))
    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "real_papers": {"status": real["status"], "per_paper": [{"id": r["id"], "review_kind": r.get("review_kind"), "headings_f1": r["headings"]["f1"], "concepts_f1": r["concepts"]["f1"]}
                                                                  for r in real["papers"] if r["ok"]],
                            "aggregate": {key: real.get(key) for key in ("headings", "concepts", "coverage", "roles")},
                            "human_reviewed": real.get("human_reviewed"), "provisional": real.get("provisional")}}


def render_gate(report):
    lines = ["REGRESSION GATE: " + ("PASSED" if report["passed"] else "FAILED")]
    for check in report["checks"]:
        lines.append(f"  [{'ok' if check['passed'] else 'FAIL'}] {check['group']:<24}{check['metric']:<24}{check['value']:.3f} (floor {check['threshold']})")
        if not check["passed"] and check["detail"]:
            lines.append(f"        what to look at: {check['detail']}")
    real = report["real_papers"]
    lines.append(f"real papers: {real['status'].upper()} " + ("(annotations approved by an AI, not a human reviewer: the floors above guard against regressions but are not validated ground truth)"
                 if real["status"] == "provisional" else "(human-reviewed annotations)" if real["status"] == "human_reviewed" else "(no scored paper)"))
    for paper in real["per_paper"]:
        lines.append(f"  {paper['id']:<18} approved by {paper['review_kind']}: headings F1 {paper['headings_f1']:.2f}, concepts F1 {paper['concepts_f1']:.2f}")
    if not report["passed"]:
        lines.append("A floor was missed: find what changed (git diff, then the named false positives and negatives above), fix the pipeline, or, if the change is intended, say why and lower the floor in thresholds.json.")
    return "\n".join(lines)
