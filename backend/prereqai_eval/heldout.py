"""Held-out PDF invariants: checks that need no annotation, on real papers the rules were not tuned on.

`heldout/manifest.json` lists CC BY 4.0 papers (GQA, Mistral 7B, Constitutional AI) with their source, licence evidence (read by an AI assistant, not a human: the manifest says so) and the
SHA-256 of each PDF. For each, the whole pipeline runs and these invariants must hold; a violation names the paper and exactly what is wrong:
* references_extracted: the bibliography was found (at least MIN_REFERENCES entries, each with text);
* no_duplicate_headings: no two sections of a paper carry the same title (a table's column header read as a heading repeats);
* no_short_headings: no heading is shorter than 3 characters once its number is removed;
* no_bibliography_only_concepts: every detected concept is named (by its name or an alias) somewhere outside the bibliography;
* evidence_quotations_verified: every evidence passage is an exact quotation of the page it cites, in a section the paper has.
Offline and deterministic. `python -m backend.prereqai_eval --heldout` prints them; `--gate` includes them."""
import hashlib
import json
import re
from pathlib import Path

HELDOUT_DIR = Path(__file__).with_name("heldout")
DEFAULT_MANIFEST = HELDOUT_DIR / "manifest.json"
MIN_REFERENCES = 10
MIN_HEADING_CHARS = 3
INVARIANTS = ("references_extracted", "no_duplicate_headings", "no_short_headings", "no_bibliography_only_concepts", "evidence_quotations_verified")
_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z](?:\.\d+)*\.?)\s+")
_BIBLIOGRAPHY = re.compile(r"^(?:references|bibliography|works cited)\b", re.IGNORECASE)


class HeldoutError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def load_manifest(path=DEFAULT_MANIFEST):
    """The manifest's papers, each with its absolute PDF path; HeldoutError listing every problem (format, licence not verified, PDF missing or not matching its SHA-256)."""
    path, problems = Path(path), []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HeldoutError([f"cannot read {path}: {error}"]) from None
    if data.get("format") != "prereqai-heldout-manifest":
        raise HeldoutError([f"{path} is not a held-out manifest"])
    papers = []
    for paper in data.get("papers", []):
        where, licence, pdf = paper.get("id", "?"), paper.get("license") or {}, paper.get("pdf") or {}
        if licence.get("status") != "verified" or licence.get("spdx") != "CC-BY-4.0" or not licence.get("evidence_url") or not licence.get("verified_by"):
            problems.append(f"{where}: the licence is not recorded as a verified CC-BY-4.0 with its evidence and who read it")
        target = path.parent / str(pdf.get("path", ""))
        if not target.is_file():
            problems.append(f"{where}: the PDF {pdf.get('path')} is missing")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != pdf.get("sha256"):
            problems.append(f"{where}: the PDF does not match its recorded SHA-256 (it was changed or replaced)")
        papers.append({**paper, "pdf_path": str(target)})
    if problems:
        raise HeldoutError(problems)
    return papers


def _title_key(title):
    return " ".join(_NUMBER.sub("", (title or "").strip()).split()).lower()


def _terms(concept):
    return [concept.name, *concept.aliases]


def check_paper(paper):
    """{invariant: [violation message]} for one analysed Paper (empty lists when it holds)."""
    from backend.concepts.concept_registry import ConceptRegistry
    from backend.evidence import build_evidence

    found = {name: [] for name in INVARIANTS}
    references = [r for r in paper.references if (r.raw_text or "").strip()]
    if len(references) < MIN_REFERENCES:
        found["references_extracted"].append(f"only {len(references)} bibliography entries were extracted (at least {MIN_REFERENCES} expected)")
    titles = [s.title for s in paper.sections]
    for title, count in sorted({t: titles.count(t) for t in titles}.items()):
        if count > 1 and _title_key(title) != "front matter":
            found["no_duplicate_headings"].append(f"the heading {title!r} appears {count} times")
    for title in titles:
        if len(_title_key(title)) < MIN_HEADING_CHARS and title != "Front Matter":
            found["no_short_headings"].append(f"the heading {title!r} is shorter than {MIN_HEADING_CHARS} characters")
    raw = "\n".join(s.content for s in paper.sections if not _BIBLIOGRAPHY.match(_NUMBER.sub("", s.title.strip()))).lower()
    body = " ".join(raw.split()) + " " + " ".join(re.sub(r"-[ \t]*\n\s*", "", raw).split())  # as printed, and with line-end hyphens joined ("atten-\ntion")
    registry = {c.name: c for c in ConceptRegistry().all()}
    for concept in paper.concepts:
        entry = registry.get(concept.name)
        terms = _terms(entry) if entry else [concept.name]
        if not any(re.search(rf"(?<![a-z0-9]){re.escape(' '.join(term.lower().split()))}s?(?![a-z0-9])", body) or re.search(rf"(?<![a-z0-9]){re.escape(term.lower().replace(' ', '-'))}", body) for term in terms):
            found["no_bibliography_only_concepts"].append(f"the concept {concept.name!r} is detected but no term of it occurs outside the bibliography")
    pages = {page.page_number: page.text for page in paper.pages}
    sections = set(titles)
    for name, passages in build_evidence(paper).items():
        for passage in passages:
            if passage["page_number"] not in pages:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} cites page {passage['page_number']}, which the paper does not have")
            elif passage["sentence"] not in pages[passage["page_number"]]:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} is not on page {passage['page_number']}: {passage['sentence'][:60]!r}")
            elif passage["section"] not in sections:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} names the section {passage['section']!r}, which the paper does not have")
    return found


def run_heldout(manifest=DEFAULT_MANIFEST):
    """{"passed", "papers": [{id, title, violations: {invariant: [...]}, ok, error}], "invariants": {name: share of papers holding it}}. A pipeline failure on a paper is a violation, not a crash."""
    from backend.pipeline import ResearchPaperPipeline

    rows = []
    for paper in load_manifest(manifest):
        row = {"id": paper["id"], "title": paper["title"], "arxiv_id": paper.get("arxiv_id"), "sha256": paper["pdf"]["sha256"], "licence": paper["license"]["spdx"],
               "licence_checked_by": paper["license"]["verified_by"], "violations": {name: [] for name in INVARIANTS}, "error": ""}
        try:
            row["violations"] = check_paper(ResearchPaperPipeline().run(paper["pdf_path"]).paper)
        except Exception as error:  # a crash is reported against the paper, with the others still checked
            row["error"] = f"{type(error).__name__}: {error}"
            row["violations"]["references_extracted"].append(f"the pipeline failed on this paper: {row['error']}")
        row["ok"] = not any(row["violations"].values())
        rows.append(row)
    return {"passed": all(r["ok"] for r in rows) and bool(rows), "papers": rows,
            "invariants": {name: (sum(1 for r in rows if not r["violations"][name]) / len(rows) if rows else 0.0) for name in INVARIANTS}}


def render_heldout(report):
    lines = ["HELD-OUT INVARIANTS: " + ("PASSED" if report["passed"] else "FAILED")]
    for row in report["papers"]:
        lines.append(f"  {row['id']:<18} arXiv {row['arxiv_id']}  {row['licence']}  sha256 {row['sha256'][:12]}  " + ("ok" if row["ok"] else "VIOLATED"))
        for name, messages in row["violations"].items():
            for message in messages:
                lines.append(f"      [{name}] {message}")
    lines.append("licences were read from the arXiv abstract pages by an AI assistant, not by a human reviewer; the papers have no annotations, so only invariants are checked")
    return "\n".join(lines)
