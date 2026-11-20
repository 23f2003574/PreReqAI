"""Real-paper benchmark: a versioned manifest of academic PDFs with verified provenance and licence, human-reviewed annotations, and an offline
runner that sends each PDF through the production pipeline and scores it. Its results are always reported apart from the synthetic evaluation.

Ground-truth integrity: an annotation is `pending_review` until a named person approves it (approve(), or --approve); pending annotations, papers
whose licence is not verified, papers without their PDF (or whose PDF does not match its recorded sha256) are listed as excluded with the reason
and take no part in any metric. Nothing here marks a machine-made annotation as reviewed.

Files (see benchmark/README.md): benchmark/manifest.json, benchmark/annotations/<paper id>.json, benchmark/pdfs/<paper id>.pdf."""
import datetime
import hashlib
import json
import re
from pathlib import Path

from .harness import scores
from .pdf_eval import check_dependencies, heading_key

BENCHMARK_DIR = Path(__file__).with_name("benchmark")
DEFAULT_MANIFEST = BENCHMARK_DIR / "manifest.json"
MANIFEST_FORMAT, ANNOTATION_FORMAT, SCHEMA_VERSION = "prereqai-benchmark-manifest", "prereqai-benchmark-annotation", 1
ROLES = ("instructional", "related", "other")
REVIEW_STATES = ("pending_review", "approved")
REVIEW_KINDS = ("human", "ai")  # who approved: only a human's approval makes an annotation reviewed ground truth; an AI's makes its scores provisional
LICENCES = ("CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-3.0", "CC0-1.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "MIT", "Apache-2.0")  # licences that allow redistribution as a test file
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class BenchmarkError(ValueError):
    """The manifest or an annotation is invalid; `problems` lists every reason, each naming its file and field."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def _read(path, expected):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BenchmarkError([f"{path}: cannot be read as JSON ({error})"]) from error
    if not isinstance(data, dict) or data.get("format") != expected or data.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError([f"{path}: must be a {expected!r} file with schema_version {SCHEMA_VERSION}"])
    return data


def _text(problems, where, value, name):
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{where}: '{name}' must be a non-empty string")
        return False
    return True


def validate_manifest(data, base=BENCHMARK_DIR):
    """Every problem of a manifest dict (missing fields, duplicates, bad licence or review data), [] when it is valid."""
    problems, seen = [], set()
    papers = data.get("papers")
    if not isinstance(papers, list) or not papers:
        return ["manifest: 'papers' must be a non-empty list"]
    for index, paper in enumerate(papers):
        where = f"paper #{index}"
        if not isinstance(paper, dict):
            problems.append(f"{where}: must be an object")
            continue
        name = paper.get("id")
        if not isinstance(name, str) or not _ID.fullmatch(name):
            problems.append(f"{where}: 'id' must be lower-case letters, digits, '-' or '_'")
        elif name in seen:
            problems.append(f"{where}: duplicate id {name!r}")
        else:
            seen.add(name)
            where = f"paper {name!r}"
        for field in ("title", "source_url"):
            _text(problems, where, paper.get(field), field)
        authors = paper.get("authors")
        if not isinstance(authors, list) or not authors or not all(isinstance(a, str) and a.strip() for a in authors):
            problems.append(f"{where}: 'authors' must be a non-empty list of names")
        publication = paper.get("publication")
        if not isinstance(publication, dict) or not _text(problems, where, publication.get("venue"), "publication.venue") \
                or not isinstance(publication.get("year"), int):
            problems.append(f"{where}: 'publication' needs a venue and an integer year")
        licence = paper.get("license")
        if not isinstance(licence, dict) or licence.get("status") not in ("verified", "unverified"):
            problems.append(f"{where}: 'license.status' must be 'verified' or 'unverified'")
        elif licence["status"] == "verified":
            if licence.get("spdx") not in LICENCES:
                problems.append(f"{where}: a verified licence must be one of {', '.join(LICENCES)}")
            if not _text(problems, where, licence.get("evidence_url"), "license.evidence_url") or not _DATE.fullmatch(str(licence.get("verified_on"))):
                problems.append(f"{where}: a verified licence needs 'evidence_url' and 'verified_on' (YYYY-MM-DD)")
        retrieved, pdf = paper.get("retrieved_on"), paper.get("pdf")
        if pdf is not None:
            if not isinstance(pdf, dict) or not _text(problems, where, pdf.get("path"), "pdf.path") or not re.fullmatch(r"[0-9a-f]{64}", str(pdf.get("sha256"))):
                problems.append(f"{where}: 'pdf' needs a path and a 64-hex sha256")
            elif Path(pdf["path"]).is_absolute() or ".." in Path(pdf["path"]).parts:
                problems.append(f"{where}: 'pdf.path' must stay inside the benchmark folder")
            if not _DATE.fullmatch(str(retrieved)):
                problems.append(f"{where}: a paper with a PDF needs 'retrieved_on' (YYYY-MM-DD)")
        if not _text(problems, where, paper.get("annotation"), "annotation"):
            continue
        if Path(paper["annotation"]).is_absolute() or ".." in Path(paper["annotation"]).parts:
            problems.append(f"{where}: 'annotation' must stay inside the benchmark folder")
    return problems


def validate_annotation(data, where="annotation"):
    """Every problem of an annotation dict, [] when it is valid. Identifiers are checked against PreReqAI's own concepts and subjects."""
    from backend.learner_profile import key, vocabulary
    from backend.concepts import ConceptRegistry

    problems = []
    if not _text(problems, where, data.get("paper_id"), "paper_id"):
        pass
    review = data.get("review")
    if not isinstance(review, dict) or review.get("status") not in REVIEW_STATES:
        problems.append(f"{where}: 'review.status' must be one of {', '.join(REVIEW_STATES)}")
    elif review["status"] == "approved" and (not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                                             or not _DATE.fullmatch(str(review.get("reviewed_on")))):
        problems.append(f"{where}: an approved annotation needs the reviewer's name and 'reviewed_on' (YYYY-MM-DD)")
    sections = data.get("sections")
    titles = {}
    if not isinstance(sections, list) or not sections:
        problems.append(f"{where}: 'sections' must be a non-empty list")
        sections = []
    for item in sections:
        if not isinstance(item, dict) or not _text(problems, where, item.get("title"), "sections[].title"):
            problems.append(f"{where}: every section needs a 'title' and a 'role'")
            continue
        if item.get("role") not in ROLES:
            problems.append(f"{where}: section {item['title']!r} has role {item.get('role')!r}; use one of {', '.join(ROLES)}")
        if heading_key(item["title"]) in titles:
            problems.append(f"{where}: duplicate section {item['title']!r}")
        titles[heading_key(item["title"])] = item["title"]
    registry, subjects = {c.name for c in ConceptRegistry().all()}, set(vocabulary().values())
    seen = set()
    for item in data.get("concepts") if isinstance(data.get("concepts"), list) else (problems.append(f"{where}: 'concepts' must be a list") or []):
        name = item.get("name") if isinstance(item, dict) else None
        if name not in registry:
            problems.append(f"{where}: concept {name!r} is not a registry concept")
            continue
        if name in seen:
            problems.append(f"{where}: duplicate concept {name!r}")
        seen.add(name)
        occurrences = item.get("occurrences", {})
        if not isinstance(occurrences, dict):
            problems.append(f"{where}: concept {name!r}: 'occurrences' must map section titles to counts")
            continue
        for section, count in occurrences.items():
            if heading_key(section) not in titles:
                problems.append(f"{where}: concept {name!r} refers to section {section!r}, which is not in 'sections'")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                problems.append(f"{where}: concept {name!r}, section {section!r}: the count must be an integer of at least 1")
    seen = set()
    for item in data.get("prerequisites") if isinstance(data.get("prerequisites"), list) else (problems.append(f"{where}: 'prerequisites' must be a list") or []):
        name = item.get("concept") if isinstance(item, dict) else None
        if name not in subjects:
            problems.append(f"{where}: prerequisite {name!r} is not a subject PreReqAI knows")
        elif name in seen:
            problems.append(f"{where}: duplicate prerequisite {name!r}")
        seen.add(name)
        if not isinstance(item, dict) or not isinstance(item.get("covered"), bool):
            problems.append(f"{where}: prerequisite {name!r} needs 'covered': true or false")
    return problems


def load_manifest(path=DEFAULT_MANIFEST):
    data = _read(path, MANIFEST_FORMAT)
    problems = validate_manifest(data)
    if problems:
        raise BenchmarkError([f"{path}: {p}" for p in problems])
    return data


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_kind(annotation):
    """"human" or "ai" for an approved annotation. One that does not say (approved before the kind was recorded) is not taken for a human's: it counts as "ai", that is, provisional."""
    kind = (annotation.get("review") or {}).get("reviewer_kind")
    return kind if kind in REVIEW_KINDS else "ai"


def approve(annotation_path, reviewer, reviewed_on=None, kind="human"):
    """Record a person's approval of a valid annotation (the only way an annotation becomes ground truth). A blank reviewer is refused."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise BenchmarkError(["approval needs the reviewer's name"])
    data = _read(annotation_path, ANNOTATION_FORMAT)
    if kind not in REVIEW_KINDS:
        raise BenchmarkError([f"the reviewer kind must be one of {', '.join(REVIEW_KINDS)}"])
    data["review"] = {"status": "approved", "reviewer": reviewer.strip(), "reviewer_kind": kind, "reviewed_on": reviewed_on or datetime.date.today().isoformat()}
    problems = validate_annotation(data, str(annotation_path))
    if problems:
        raise BenchmarkError(problems)
    Path(annotation_path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def register_paper(manifest_path, pdf_path, paper_id, licence_spdx, licence_evidence_url, licence_checked_by, metadata=None, checked_on=None):
    """Put a PDF into the benchmark: copy it to pdfs/<id>.pdf, record its SHA-256, retrieval date and licence, and make sure a `pending_review` annotation exists.
    The licence is recorded as verified only on the word of the person named in `licence_checked_by`, who has read the licence at `licence_evidence_url`: this
    function checks nothing online and never approves an annotation (that stays `approve`'s job). `metadata` (title, authors, source_url, venue, year) is needed
    for an id the manifest does not list yet. Nothing is written unless the whole manifest validates afterwards."""
    manifest_path, pdf_path, today = Path(manifest_path), Path(pdf_path), checked_on or datetime.date.today().isoformat()
    problems = []
    if not isinstance(paper_id, str) or not _ID.fullmatch(paper_id):
        problems.append("the id must be lower-case letters, digits, '-' or '_'")
    if licence_spdx not in LICENCES:
        problems.append(f"the licence must be one of {', '.join(LICENCES)} (a paper without a redistribution licence cannot be added)")
    for value, label in ((licence_evidence_url, "the licence evidence link"), (licence_checked_by, "the name of the person who checked the licence")):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label} is required")
    try:
        raw = pdf_path.read_bytes()
    except OSError as error:
        raise BenchmarkError([f"cannot read {pdf_path}: {getattr(error, 'strerror', None) or error}"]) from None
    if not raw.startswith(b"%PDF-"):
        problems.append(f"{pdf_path} is not a PDF file")
    manifest = _read(manifest_path, MANIFEST_FORMAT)
    entry = next((paper for paper in manifest.get("papers", []) if paper.get("id") == paper_id), None)
    if entry is not None and entry.get("license", {}).get("status") == "verified":
        problems.append(f"{paper_id!r} already has a verified licence and PDF; edit the manifest by hand to replace them")
    if entry is None:
        needed = ("title", "authors", "source_url", "venue", "year")
        if not metadata or any(not metadata.get(name) for name in needed):
            problems.append(f"a new paper needs {', '.join(needed)}")
    if problems:
        raise BenchmarkError(problems)
    base = manifest_path.parent
    if entry is None:
        entry = {"id": paper_id, "title": metadata["title"], "authors": list(metadata["authors"]), "source_url": metadata["source_url"],
                 "publication": {"venue": metadata["venue"], "year": int(metadata["year"])}, "annotation": f"annotations/{paper_id}.json"}
        manifest["papers"].append(entry)
    entry["license"] = {"status": "verified", "spdx": licence_spdx, "evidence_url": licence_evidence_url.strip(), "verified_on": today, "verified_by": licence_checked_by.strip()}
    entry["retrieved_on"], entry["pdf"] = today, {"path": f"pdfs/{paper_id}.pdf", "sha256": hashlib.sha256(raw).hexdigest()}
    found = validate_manifest(manifest, base)
    if found:
        raise BenchmarkError(found)
    (base / "pdfs").mkdir(parents=True, exist_ok=True)
    (base / entry["pdf"]["path"]).write_bytes(raw)
    annotation = base / entry["annotation"]
    if not annotation.exists():  # never replaces an annotation a person has worked on
        annotation.parent.mkdir(parents=True, exist_ok=True)
        annotation.write_text(json.dumps({"format": ANNOTATION_FORMAT, "schema_version": 1, "paper_id": paper_id, "review": {"status": "pending_review"},
                                          "sections": [{"title": "Abstract", "role": "other"}], "concepts": [], "prerequisites": []}, indent=2) + "\n", encoding="utf-8")
    temp = manifest_path.with_name(f".{manifest_path.name}.tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temp.replace(manifest_path)
    return entry


def status(manifest_path=DEFAULT_MANIFEST):
    """[{id, ready, blockers: [...]}] for every paper: everything still missing before it can be scored (licence, PDF, hash, annotation content and review), not just the first."""
    manifest = load_manifest(manifest_path)
    base, rows = Path(manifest_path).parent, []
    for paper in manifest["papers"]:
        blockers = []
        if paper["license"]["status"] != "verified":
            blockers.append("licence not verified: check the licence at the source, then `--register PDF --id ...`")
        pdf = paper.get("pdf")
        if not pdf or not (base / pdf["path"]).is_file():
            blockers.append("PDF not in the benchmark folder")
        elif _sha256(base / pdf["path"]) != pdf["sha256"]:
            blockers.append("PDF does not match its recorded sha256")
        try:
            annotation = _read(base / paper["annotation"], ANNOTATION_FORMAT)
            if validate_annotation(annotation, paper["annotation"]):
                blockers.append("annotation is invalid: " + validate_annotation(annotation, paper["annotation"])[0])
            elif annotation["review"]["status"] != "approved":
                blockers.append("annotation is pending_review: annotate it from the paper, then a person runs `--approve`")
            elif not annotation.get("concepts"):
                blockers.append("annotation is approved but lists no concepts")
        except BenchmarkError as error:
            blockers.append(f"annotation unusable: {error}")
        rows.append({"id": paper["id"], "ready": not blockers, "blockers": blockers})
    return rows


def render_status(rows):
    ready = sum(row["ready"] for row in rows)
    lines = [f"BENCHMARK STATUS: {ready} of {len(rows)} papers ready to be scored (scoring needs a verified licence, the PDF and a person-approved annotation)"]
    for row in rows:
        lines.append(f"  {row['id']}: " + ("ready" if row["ready"] else ""))
        lines.extend(f"      - {blocker}" for blocker in row["blockers"])
    return "\n".join(lines)


def eligibility(paper, manifest_dir):
    """(annotation or None, why not): a paper takes part in the metrics only with a verified licence, its PDF (matching its sha256) and an approved annotation."""
    if paper["license"]["status"] != "verified":
        return None, "licence not verified"
    pdf = paper.get("pdf")
    if not pdf or not (manifest_dir / pdf["path"]).is_file():
        return None, "PDF not available"
    if _sha256(manifest_dir / pdf["path"]) != pdf["sha256"]:
        return None, "PDF does not match its recorded sha256"
    try:
        annotation = _read(manifest_dir / paper["annotation"], ANNOTATION_FORMAT)
    except BenchmarkError as error:
        return None, f"annotation unusable: {error}"
    problems = validate_annotation(annotation, paper["annotation"])
    if problems:
        return None, "annotation invalid: " + problems[0]
    if annotation["paper_id"] != paper["id"]:
        return None, "annotation belongs to another paper"
    if annotation["review"]["status"] != "approved":
        return None, "annotation pending_review"
    return annotation, ""


def _set_scores(expected, found):
    result = scores(expected, found)
    result["missed"], result["spurious"] = sorted(map(str, set(expected) - set(found))), sorted(map(str, set(found) - set(expected)))
    return result


def heading_depth(title):
    """1 for a section ("5 Theory", "A Proofs", "Introduction"), 2 or more for a numbered sub-section ("5.2 ...", "A.4 ...")."""
    match = re.match(r"^\s*(?:\d+|[A-Z])((?:\.\d+)+)(?=\s)", str(title))
    return 1 + match.group(1).count(".") if match else 1


def score_paper(annotation, paper):
    """The metrics of one analysed paper against an approved annotation; false negatives and positives are listed by name."""
    from backend.concepts.rule_based_concept_detector import section_mentions
    from backend.prerequisites.missing_prerequisite_analyzer import section_role

    top_only = annotation.get("heading_scope") == "top-level"  # such an annotation lists the numbered sections, not their sub-sections ("5.2 ...")
    found_titles = {heading_key(s.title): s.title for s in paper.sections
                    if heading_key(s.title) != "front matter" and not (top_only and heading_depth(s.title) > 1)}
    expected = {heading_key(s["title"]): s["role"] for s in annotation["sections"]}
    matched = sorted(set(expected) & set(found_titles))
    wrong = [k for k in matched if section_role(found_titles[k]) != expected[k]]
    expected_counts = {(c["name"], heading_key(s)): n for c in annotation["concepts"] for s, n in c.get("occurrences", {}).items()}
    found_counts = {(name, heading_key(title)): n for title, found in section_mentions(paper).items() for name, n in found["concepts"].items()}
    covered = {m.concept for m in paper.missing_prerequisites if m.satisfied}
    exact = [pair for pair in expected_counts if found_counts.get(pair) == expected_counts[pair]]
    return {
        "headings": _set_scores(expected, found_titles),
        "roles": {"correct": len(matched) - len(wrong), "total": len(expected), "wrong": wrong,
                  "accuracy": round((len(matched) - len(wrong)) / len(expected), 3)},
        "concepts": _set_scores({c["name"] for c in annotation["concepts"]}, {c.name for c in paper.concepts}),
        "occurrences": {"annotated": len(expected_counts), "exact": len(exact),
                        "wrong": sorted(f"{c} in {s}: expected {expected_counts[(c, s)]}, found {found_counts.get((c, s), 0)}" for c, s in expected_counts if (c, s) not in exact)},
        # An annotation that lists no prerequisites says nothing about coverage: it is reported as not annotated, never as everything being a false positive.
        "coverage": _set_scores({p["concept"] for p in annotation["prerequisites"] if p["covered"]}, covered) if annotation["prerequisites"] else None,
    }


def _micro(rows, key):
    tp, fp, fn = (sum(r[key][f] for r in rows) for f in ("tp", "fp", "fn"))
    precision, recall = (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def evaluate_benchmark(manifest_path=DEFAULT_MANIFEST):
    """{'mode': 'benchmark', 'real_papers': True, 'papers': [...], 'excluded': [{id, reason}], aggregate scores}; offline and deterministic."""
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    base, rows, excluded = manifest_path.parent, [], []
    ready = []
    for paper in manifest["papers"]:
        annotation, why = eligibility(paper, base)
        (ready.append((paper, annotation)) if annotation else excluded.append({"id": paper["id"], "title": paper["title"], "reason": why}))
    if ready:
        check_dependencies()
        from backend.pipeline import ResearchPaperPipeline
    for paper, annotation in ready:
        row = {"id": paper["id"], "title": paper["title"], "ok": True, "error": "", "review_kind": review_kind(annotation)}
        try:
            row.update(score_paper(annotation, ResearchPaperPipeline().run(str(base / paper["pdf"]["path"])).paper))
        except Exception as error:  # a pipeline failure on a paper is a result, not a crash of the benchmark
            row.update(ok=False, error=f"{type(error).__name__}: {error}")
        rows.append(row)
    scored = [r for r in rows if r["ok"]]
    report = {"mode": "benchmark", "real_papers": True, "papers": rows, "excluded": excluded,
              "counts": {"manifest": len(manifest["papers"]), "evaluated": len(rows), "excluded": len(excluded)}}
    if scored:
        report.update({key: value for key, value in _aggregate(scored).items() if key != "paper_ids"})
        # Whose approval stands behind the numbers: only a human reviewer's annotations are reviewed ground truth; an AI's (or one that does not say) make the scores provisional.
        human, provisional = [r for r in scored if r["review_kind"] == "human"], [r for r in scored if r["review_kind"] != "human"]
        report["human_reviewed"] = _aggregate(human) if human else None
        report["provisional"] = _aggregate(provisional) if provisional else None
        report["status"] = "provisional" if provisional else "human_reviewed"
    else:
        report["status"] = "no_scores"
    return report


def _aggregate(rows):
    correct, total = sum(r["roles"]["correct"] for r in rows), sum(r["roles"]["total"] for r in rows)
    annotated = [r for r in rows if r["coverage"] is not None]
    return {"paper_ids": [r["id"] for r in rows], "headings": _micro(rows, "headings"), "concepts": _micro(rows, "concepts"),
            "coverage": _micro(annotated, "coverage") if annotated else None, "roles": {"correct": correct, "total": total, "accuracy": round(correct / total, 3) if total else 1.0}}


def render_benchmark(report):
    lines = ["REAL-PAPER BENCHMARK (approved annotations only; separate from the synthetic evaluation)",
             f"{report['counts']['evaluated']} of {report['counts']['manifest']} papers evaluated, {report['counts']['excluded']} excluded"]
    if report.get("status") == "provisional":
        lines.append("PROVISIONAL: " + ", ".join(report["provisional"]["paper_ids"]) + " rest on annotations approved by an AI (or by someone not recorded as human), not on a human reviewer's; "
                     + ("human-reviewed: " + ", ".join(report["human_reviewed"]["paper_ids"]) if report.get("human_reviewed") else "no paper is human-reviewed yet") + ".")
    for row in report["papers"]:
        if not row["ok"]:
            lines.append(f"{row['id']:<18}PIPELINE FAILED: {row['error']}")
            continue
        lines.append(f"{row['id']:<18}headings F1={row['headings']['f1']:.2f}  roles {row['roles']['correct']}/{row['roles']['total']}  concepts F1={row['concepts']['f1']:.2f}  "
                     f"occurrences {row['occurrences']['exact']}/{row['occurrences']['annotated']}  "
                     + (f"coverage P={row['coverage']['precision']:.2f} R={row['coverage']['recall']:.2f}" if row["coverage"] else "coverage not annotated"))
        for label, key in (("headings", "headings"), ("concepts", "concepts"), ("coverage", "coverage")):
            for field, tag in (("missed", "false negatives"), ("spurious", "false positives")):
                if row[key] and row[key][field]:
                    lines.append(f"{'':<18}  {label} {tag}: {row[key][field]}")
        for item in row["occurrences"]["wrong"]:
            lines.append(f"{'':<18}  occurrence mismatch: {item}")
    if "concepts" in report:
        for key in ("headings", "concepts", "coverage"):
            m = report[key]
            if m is None:
                lines.append(f"{'AGGREGATE':<18}{key:<10}not annotated for any evaluated paper")
                continue
            lines.append(f"{'AGGREGATE':<18}{key:<10}P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
        lines.append(f"{'AGGREGATE':<18}{'roles':<10}{report['roles']['correct']}/{report['roles']['total']} = {report['roles']['accuracy']:.2f}")
    else:
        lines.append("No paper is evaluable yet, so there are no metrics: none has a verified licence, its PDF and an approved annotation.")
    for item in report["excluded"]:
        lines.append(f"excluded: {item['id']}: {item['reason']}")
    return "\n".join(lines)
