"""PDF mode of the evaluation: synthetic academic PDFs go through the real pipeline (PDF ingestion, section parsing, concept and
prerequisite detection, section-aware coverage) and the result is compared with the fixtures' annotations.

Read this first: the PDFs are generated for this repository (see pdf_fixtures.py). A good score shows the pipeline handles these layouts;
it is not validation on real published papers, and nothing here replaces that."""
import re
import tempfile

from backend.parsing.scientific_section_parser import ScientificSectionParser  # noqa: F401  (the real parser runs inside the pipeline)
from backend.prerequisites.missing_prerequisite_analyzer import section_role

from .harness import scores
from .pdf_fixtures import FIXTURES, write_fixture_pdfs

NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXivx]+\.)\s+")
IGNORED_TITLES = {"front matter"}  # text before the first heading is not a heading the fixtures annotate


class PdfDependencyError(RuntimeError):
    """PyMuPDF (which reads and writes the PDFs) is not installed; the message says how to install it."""


def check_dependencies():
    try:
        import pymupdf  # noqa: F401
    except ImportError as error:
        raise PdfDependencyError("PDF evaluation needs PyMuPDF, which is not installed. Run: pip install -r requirements.txt") from error


def heading_key(title):
    """A heading compared without its number and letter case: "4 Experiments on CIFAR-10" and "Experiments on CIFAR-10" are the same."""
    return NUMBER.sub("", (title or "").strip()).strip().lower()


def score_fixture(fixture, paper):
    """The measurements of one analysed paper against its fixture, from the paper's own sections, concepts and coverage entries."""
    found_titles = {heading_key(s.title): s.title for s in paper.sections if heading_key(s.title) not in IGNORED_TITLES}
    expected = {heading_key(title): role for title, role in fixture["sections"]}
    headings = scores(expected, found_titles)
    headings["missed"], headings["spurious"] = sorted(set(expected) - set(found_titles)), sorted(set(found_titles) - set(expected))
    matched = sorted(set(expected) & set(found_titles))
    wrong = [key for key in matched if section_role(found_titles[key]) != expected[key]]
    roles = {"correct": len(matched) - len(wrong), "total": len(expected), "wrong": wrong, "accuracy": round((len(matched) - len(wrong)) / len(expected), 3) if expected else 1.0}
    concepts = scores(fixture["concepts"], {c.name for c in paper.concepts})
    covered = {m.concept for m in paper.missing_prerequisites if m.satisfied}
    coverage = scores(fixture["covered"], covered)
    coverage["missed"], coverage["spurious"] = sorted(set(fixture["covered"]) - covered), sorted(covered - set(fixture["covered"]))
    return {"headings": headings, "roles": roles, "concepts": concepts, "coverage": coverage}


def _micro(rows, key):
    tp, fp, fn = (sum(row[key][field] for row in rows) for field in ("tp", "fp", "fn"))
    precision, recall = (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn}


def evaluate_pdf(fixtures=None):
    """{'mode': 'pdf', 'synthetic': True, 'fixtures': [...], 'headings', 'concepts', 'coverage': micro scores, 'roles': accuracy,
    'pipeline': outcomes}. Offline and deterministic: the same fixtures give the same numbers."""
    check_dependencies()
    from backend.pipeline import ResearchPaperPipeline

    rows = []
    with tempfile.TemporaryDirectory() as directory:
        for fixture_id, path in write_fixture_pdfs(directory, fixtures).items():
            fixture = next(f for f in (fixtures or FIXTURES) if f["id"] == fixture_id)
            row = {"id": fixture_id, "title": fixture["title"], "columns": fixture["columns"], "ok": True, "error": ""}
            try:
                paper = ResearchPaperPipeline().run(str(path)).paper
                row.update(score_fixture(fixture, paper))
            except Exception as error:  # a pipeline failure is a result of the evaluation, not a crash of it
                row.update(ok=False, error=f"{type(error).__name__}: {error}")
                empty = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(fixture["concepts"])}
                row.update(headings=dict(empty, fn=len(fixture["sections"])), concepts=empty, coverage=dict(empty, fn=len(fixture["covered"])),
                           roles={"correct": 0, "total": len(fixture["sections"]), "wrong": [], "accuracy": 0.0})
            rows.append(row)
    correct, total = sum(r["roles"]["correct"] for r in rows), sum(r["roles"]["total"] for r in rows)
    return {"mode": "pdf", "synthetic": True, "fixtures": rows,
            "headings": _micro(rows, "headings"), "concepts": _micro(rows, "concepts"), "coverage": _micro(rows, "coverage"),
            "roles": {"correct": correct, "total": total, "accuracy": round(correct / total, 3) if total else 1.0},
            "pipeline": {"succeeded": sum(r["ok"] for r in rows), "total": len(rows)}}


def render_pdf(report):
    lines = ["PDF evaluation (SYNTHETIC PDFs written for this repository; not validation on real published papers)"]
    for row in report["fixtures"]:
        if not row["ok"]:
            lines.append(f"{row['id']:<16}PIPELINE FAILED: {row['error']}")
            continue
        r = row
        lines.append(f"{row['id']:<16}{row['columns']} col  headings F1={r['headings']['f1']:.2f}  roles {r['roles']['correct']}/{r['roles']['total']}  "
                     f"concepts F1={r['concepts']['f1']:.2f}  coverage P={r['coverage']['precision']:.2f} R={r['coverage']['recall']:.2f}")
        for label, key in (("headings", "headings"), ("coverage", "coverage")):
            for field in ("missed", "spurious"):
                if r[key].get(field):
                    lines.append(f"{'':<16}  {label} {field}: {r[key][field]}")
        if r["roles"]["wrong"]:
            lines.append(f"{'':<16}  wrong role: {r['roles']['wrong']}")
    for key in ("headings", "concepts", "coverage"):
        m = report[key]
        lines.append(f"{'MICRO':<16}{key:<10}P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
    lines.append(f"{'MICRO':<16}{'roles':<10}{report['roles']['correct']}/{report['roles']['total']} = {report['roles']['accuracy']:.2f}")
    lines.append(f"{'PIPELINE':<16}{report['pipeline']['succeeded']}/{report['pipeline']['total']} fixtures analysed")
    return "\n".join(lines)
