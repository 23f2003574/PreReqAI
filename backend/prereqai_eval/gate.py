"""The regression gate: `python -m backend.prereqai_eval --gate` scores the pipeline on gold data that ships with the repository and fails (exit code 1) when a score falls below its floor in
thresholds.json. Offline and deterministic (no network, no model, no randomness): the same code gives the same numbers.

Five groups, reported apart (the fifth, heldout_invariants, is in heldout.py):
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


def heldout_checks(checks, floors, manifest=None):
    """Add one check per held-out invariant (the share of papers where it holds must reach its floor, 1.0: every paper) and return the held-out report, or None when its manifest is unusable
    (then the failure is a check of its own, with the reasons)."""
    from . import heldout

    try:
        report = heldout.run_heldout(manifest or heldout.DEFAULT_MANIFEST)
    except heldout.HeldoutError as error:
        checks.append({"group": "heldout_invariants", "metric": "manifest", "value": 0.0, "threshold": 1.0, "passed": False, "detail": "; ".join(error.problems)})
        return None
    for name in heldout.INVARIANTS:
        broken = [f"{row['id']}: {message}" for row in report["papers"] for message in row["violations"][name]]
        _check(checks, "heldout_invariants", name, report["invariants"][name], floors.get(name, 1.0), "; ".join(broken[:6]) + (f"; and {len(broken) - 6} more" if len(broken) > 6 else ""))
    caught = [flag for row in report["papers"] for flag in (row.get("self_test") or {}).values()]
    missed = [f"{row['id']}: {name} was not reported" for row in report["papers"] for name, flag in (row.get("self_test") or {}).items() if not flag]
    _check(checks, "heldout_invariants", "gate_detects_degradation", (sum(caught) / len(caught)) if caught else 0.0, 1.0, "; ".join(missed) or "no paper passed, so the degradation self-test did not run")
    return report


def retrieval_checks(checks, manifest=None):
    """Retrieval checks on the held-out papers, by comparing systems with each other so no absolute score has to be guessed: the hybrid search must recall at least as many gold passages as the
    lexical one it extends, and every passage either returns must be an exact quotation of its page. Returns the measurements, or None when the papers cannot be analysed."""
    from . import heldout, retrieval_benchmark
    from backend.pipeline import ResearchPaperPipeline

    try:
        papers = [ResearchPaperPipeline().run(p["pdf_path"]).paper for p in heldout.load_manifest(manifest or heldout.DEFAULT_MANIFEST)]
    except heldout.HeldoutError as error:
        checks.append({"group": "retrieval", "metric": "papers", "value": 0.0, "threshold": 1.0, "passed": False, "detail": "; ".join(error.problems)})
        return None
    report = retrieval_benchmark.evaluate(papers)
    lexical, hybrid = report["systems"]["lexical"], report["systems"]["hybrid"]
    detail = (f"{report['questions']} questions: lexical recall@{report['k']} {lexical['recall_at_k']:.3f}, hybrid {hybrid['recall_at_k']:.3f}; by style lexical {lexical['recall_by_style']}, "
              f"hybrid {hybrid['recall_by_style']}")
    _check(checks, "retrieval", "hybrid_recall_not_below_lexical", round(hybrid["recall_at_k"], 3), round(lexical["recall_at_k"], 3), detail)  # both rounded as the report prints them, so the check and the report agree
    _check(checks, "retrieval", "quotations_verified", min(lexical["quotations_verified"], hybrid["quotations_verified"]), 1.0, detail)
    _check(checks, "retrieval", "questions_generated", float(report["questions"]), 6.0, detail)
    return report


def real_retrieval_checks(checks, floors):
    """Retrieval on the six real papers (retrieval_real.py): per paper the hybrid search must recall at least as many gold phrases as the lexical one, every returned passage must be an exact quotation,
    and the question set must not shrink. No absolute recall floor is held: none had been measured when this was written. Returns the measurements, or None when the papers cannot be analysed."""
    from backend.pipeline import ResearchPaperPipeline

    from . import retrieval_real

    data = retrieval_real.load()
    paths = retrieval_real.pdf_paths({q["paper"] for q in data["questions"]})
    try:
        papers = {paper_id: ResearchPaperPipeline().run(path).paper for paper_id, path in paths.items()}
    except Exception as error:  # a paper that cannot be analysed is a failed check, never a crash of the gate
        checks.append({"group": "retrieval_real", "metric": "papers", "value": 0.0, "threshold": 1.0, "passed": False, "detail": f"{type(error).__name__}: {error}"})
        return None
    report = retrieval_real.evaluate(papers, data)
    lexical, hybrid = report["systems"]["lexical"], report["systems"]["hybrid"]
    detail = (f"{report['questions']} questions over {len(report['papers'])} papers, recall@{report['k']} lexical {lexical['recall_at_k']:.3f} hybrid {hybrid['recall_at_k']:.3f}, MRR lexical "
              f"{lexical['mrr']:.3f} hybrid {hybrid['mrr']:.3f}, gold phrase in extracted text {report['gold_in_text']:.3f}")
    for paper_id in report["papers"]:
        a, b = lexical["by_paper"][paper_id]["recall_at_k"], hybrid["by_paper"][paper_id]["recall_at_k"]
        _check(checks, "retrieval_real", f"hybrid_not_below_lexical:{paper_id}", b, a, f"{paper_id}: lexical {a}, hybrid {b}; {detail}")
    _check(checks, "retrieval_real", "quotations_verified", min(lexical["quotations_verified"], hybrid["quotations_verified"]), 1.0, detail)
    _check(checks, "retrieval_real", "questions", float(report["questions"]), float(floors.get("questions", 30)), "the real-paper question set must not shrink: " + detail)
    return report


def math_checks(checks, floors):
    """Precision and recall of the mathematical-subtopic rules on the labelled equations (math_eval.py). The equations are AI-written and unreviewed, not extracted from real PDFs: the floors guard the
    rules against regressions, they say nothing about real papers (those are reported as not annotated)."""
    from . import math_eval

    report = math_eval.evaluate()
    detail = f"{report['equations']} equations ({report['status']}); false positives {report['false_positives'][:5]}; false negatives {report['false_negatives'][:5]}"
    _check(checks, "math_subtopics", "precision", report["precision"], floors.get("precision", 0.97), detail)
    _check(checks, "math_subtopics", "recall", report["recall"], floors.get("recall", 0.97), detail)
    _check(checks, "math_subtopics", "equations", float(report["equations"]), float(floors.get("equations", 30)), "the labelled equation set must not shrink")


def graph_checks(checks, floors):
    """The prerequisite graph: it must validate (no unknown target, cycle, duplicate or target without study hours) and the share of registry concepts with a rule must reach its floor; the concepts
    without a rule are named, because their prerequisites are unknown, not absent."""
    from backend.prerequisites import prerequisite_graph

    problems = prerequisite_graph.validate(prerequisite_graph.entries())
    _check(checks, "prerequisite_graph", "graph_valid", 0.0 if problems else 1.0, floors.get("graph_valid", 1.0), "; ".join(problems[:6]))
    covered = prerequisite_graph.coverage()
    _check(checks, "prerequisite_graph", "rule_coverage", covered["ratio"], floors.get("rule_coverage", 0.98), f"{covered['with_rules']} of {covered['concepts']} registry concepts have a rule; without: {covered['without_rules']}")


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
        _check(checks, "real_papers_provisional", "headings_precision", real["headings"]["precision"], group["headings_precision"], "spurious headings: " + worst("headings", "spurious"))
        _check(checks, "real_papers_provisional", "concepts_precision", real["concepts"]["precision"], group["concepts_precision"], "false positives: " + worst("concepts", "spurious"))
        _check(checks, "real_papers_provisional", "concepts_recall", real["concepts"]["recall"], group["concepts_recall"], "false negatives: " + worst("concepts", "missed"))
        _check(checks, "real_papers_provisional", "roles_accuracy", real["roles"]["accuracy"], group["roles_accuracy"], "wrong roles: " + worst("roles", "wrong"))
    held = heldout_checks(checks, floors.get("heldout_invariants", {}))
    retrieval_checks(checks)
    graph_checks(checks, floors.get("prerequisite_graph", {}))
    math_checks(checks, floors.get("math_subtopics", {}))
    measured = real_retrieval_checks(checks, floors.get("retrieval_real", {}))
    return {"passed": all(c["passed"] for c in checks), "checks": checks, "retrieval_real": measured, "heldout": held and {"papers": [{k: row[k] for k in ("id", "arxiv_id", "licence", "licence_checked_by", "sha256", "ok")} for row in held["papers"]]},
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
    for paper in (report.get("heldout") or {}).get("papers", []):
        lines.append(f"held-out {paper['id']:<18} arXiv {paper['arxiv_id']} {paper['licence']} sha256 {paper['sha256'][:12]}: licence read by {paper['licence_checked_by'].split(',')[0]} (not a human reviewer)")
    measured = report.get("retrieval_real")
    if measured:
        lexical, hybrid = measured["systems"]["lexical"], measured["systems"]["hybrid"]
        lines.append(f"retrieval on real papers ({measured['questions']} AI-written, unreviewed questions, no absolute floor held): recall@{measured['k']} lexical {lexical['recall_at_k']:.3f}, hybrid {hybrid['recall_at_k']:.3f}; "
                     f"MRR lexical {lexical['mrr']:.3f}, hybrid {hybrid['mrr']:.3f}; gold phrase in extracted text {measured['gold_in_text']:.3f}")
        for paper_id in measured["papers"]:
            lines.append(f"  {paper_id:<18} lexical recall {lexical['by_paper'][paper_id]['recall_at_k']:.2f} MRR {lexical['by_paper'][paper_id]['mrr']:.2f}; hybrid recall {hybrid['by_paper'][paper_id]['recall_at_k']:.2f} MRR {hybrid['by_paper'][paper_id]['mrr']:.2f}")
    real = report["real_papers"]
    lines.append(f"real papers: {real['status'].upper()} " + ("(annotations approved by an AI, not a human reviewer: the floors above guard against regressions but are not validated ground truth)"
                 if real["status"] == "provisional" else "(human-reviewed annotations)" if real["status"] == "human_reviewed" else "(no scored paper)"))
    for paper in real["per_paper"]:
        lines.append(f"  {paper['id']:<18} approved by {paper['review_kind']}: headings F1 {paper['headings_f1']:.2f}, concepts F1 {paper['concepts_f1']:.2f}")
    if not report["passed"]:
        lines.append("A floor was missed: find what changed (git diff, then the named false positives and negatives above), fix the pipeline, or, if the change is intended, say why and lower the floor in thresholds.json.")
    return "\n".join(lines)
