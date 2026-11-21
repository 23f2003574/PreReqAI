"""Held-out PDF invariants: checks that need no annotation, on real papers the rules were not tuned on.

`heldout/manifest.json` lists CC BY 4.0 papers (GQA, Mistral 7B, Constitutional AI) with their source, licence evidence (read by an AI assistant, not a human: the manifest says so) and the
SHA-256 of each PDF. For each, the whole pipeline runs and these invariants must hold; a violation names the paper and exactly what is wrong:
* references_extracted: the bibliography was found (at least MIN_REFERENCES entries, each with text);
* no_duplicate_headings: no two sections of a paper carry the same title (a table's column header read as a heading repeats);
* no_short_headings: no heading is shorter than 3 characters once its number is removed;
* no_bibliography_only_concepts: every detected concept is named (by its name or an alias) somewhere outside the bibliography;
* evidence_quotations_verified: every evidence passage is an exact quotation of the page it cites, in a section the paper has;
* informative_extraction: the result is not empty (DEFAULT_FLOORS): enough sections, concepts, citations that resolve to an extracted reference and evidence passages, the title found
  (in the PDF metadata or printed on page 1) and an abstract of some length. Passing the other invariants alone says only that nothing was wrong, not that anything was found.
`self_test` damages an analysed paper in six ways and proves the invariants notice each one.
Offline and deterministic. `python -m backend.prereqai_eval --heldout` prints them; `--gate` includes them."""
import hashlib
import json
import re
from pathlib import Path

HELDOUT_DIR = Path(__file__).with_name("heldout")
DEFAULT_MANIFEST = HELDOUT_DIR / "manifest.json"
MIN_REFERENCES = 10
MIN_HEADING_CHARS = 3
INVARIANTS = ("references_extracted", "no_duplicate_headings", "no_short_headings", "no_bibliography_only_concepts", "evidence_quotations_verified", "informative_extraction")
# The invariants above hold trivially for an empty result (no sections, no concepts, nothing to quote), so informative_extraction requires the extraction to have produced something:
# per paper, at least these floors (a manifest paper may set its own under "floors"). They sit far below what such papers yield; they exist to stop an empty result passing.
DEFAULT_FLOORS = {"sections": 4, "concepts": 3, "resolved_citations": 2, "evidence_passages": 3, "title_chars": 8, "abstract_chars": 150}
NO_FLOORS = dict.fromkeys(DEFAULT_FLOORS, 0)  # for tests that exercise one invariant on a small synthetic paper
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


def check_paper(paper, floors=None, expected_title=""):
    """{invariant: [violation message]} for one analysed Paper (empty lists when it holds). `floors` overrides DEFAULT_FLOORS keys; `expected_title` is the title the paper is known by."""
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
    evidence = build_evidence(paper)
    _informative(paper, found["informative_extraction"], {**DEFAULT_FLOORS, **(floors or {})}, expected_title, sum(len(p) for p in evidence.values()))
    for name, passages in evidence.items():
        for passage in passages:
            if passage["page_number"] not in pages:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} cites page {passage['page_number']}, which the paper does not have")
            elif passage["sentence"] not in pages[passage["page_number"]]:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} is not on page {passage['page_number']}: {passage['sentence'][:60]!r}")
            elif passage["section"] not in sections:
                found["evidence_quotations_verified"].append(f"{name}: passage {passage['passage_id']} names the section {passage['section']!r}, which the paper does not have")
    return found


def _informative(paper, found, floors, expected_title, passages):
    sections = [s for s in paper.sections if s.title != "Front Matter" or s.content.strip()]
    if len(sections) < floors["sections"]:
        found.append(f"only {len(sections)} sections were found (at least {floors['sections']} expected)")
    if len(paper.concepts) < floors["concepts"]:
        found.append(f"only {len(paper.concepts)} concepts were detected (at least {floors['concepts']} expected)")
    known = {r.reference_number for r in paper.references}
    resolved = len({c.reference_number for c in paper.citations if c.reference_number in known})
    if resolved < floors["resolved_citations"]:
        found.append(f"only {resolved} cited references were linked to an extracted bibliography entry (at least {floors['resolved_citations']} expected)")
    if passages < floors["evidence_passages"]:
        found.append(f"only {passages} evidence passages were found (at least {floors['evidence_passages']} expected)")
    first = " ".join(next((p.text for p in paper.pages if p.page_number == 1), "").lower().split())
    title = (getattr(getattr(paper, "metadata", None), "title", "") or "").strip()
    printed = bool(expected_title) and " ".join(expected_title.lower().split()[:5]) in first
    if len(title) < floors["title_chars"] and not printed:
        found.append("no title was found in the PDF metadata or on page 1")
    abstract = max((len(s.content.strip()) for s in paper.sections if re.match(r"abstract\b", _NUMBER.sub("", s.title.strip()), re.IGNORECASE)), default=0)
    if abstract < floors["abstract_chars"] and "abstract" in first:  # an abstract the section parser left in the front matter
        abstract = max((len(s.content.strip()) for s in paper.sections if s.title == "Front Matter"), default=0)
    if abstract < floors["abstract_chars"]:
        found.append(f"no abstract of at least {floors['abstract_chars']} characters was found")


def degradations():
    """{name: function(paper) returning a copy of an analysed paper damaged in one way}: what a broken extraction looks like. check_paper must report each."""
    from copy import deepcopy

    def damage(**changes):
        def apply(paper):
            copy = deepcopy(paper)
            for key, value in changes.items():
                setattr(copy, key, value)
            return copy
        return apply

    def untitled(paper):
        copy = damage(sections=[s for s in paper.sections if not re.match(r"abstract\b", s.title, re.IGNORECASE) and s.title != "Front Matter"], pages=[])(paper)
        copy.metadata = None
        return copy

    return {"no concepts": damage(concepts=[]), "no sections": damage(sections=[]), "no resolved citations": damage(citations=[]), "no title or abstract": untitled,
            "no references": damage(references=[]), "no text": damage(pages=[], sections=[], concepts=[])}


def self_test(paper, floors=None, expected_title=""):
    """{degradation: whether check_paper reported it} for an analysed paper that itself passes; proves the held-out invariants are able to fail."""
    return {name: any(check_paper(apply(paper), floors, expected_title).values()) for name, apply in degradations().items()}


def run_heldout(manifest=DEFAULT_MANIFEST):
    """{"passed", "papers": [{id, title, violations: {invariant: [...]}, ok, error}], "invariants": {name: share of papers holding it}}. A pipeline failure on a paper is a violation, not a crash."""
    from backend.pipeline import ResearchPaperPipeline

    rows = []
    for paper in load_manifest(manifest):
        row = {"id": paper["id"], "title": paper["title"], "arxiv_id": paper.get("arxiv_id"), "sha256": paper["pdf"]["sha256"], "licence": paper["license"]["spdx"],
               "licence_checked_by": paper["license"]["verified_by"], "violations": {name: [] for name in INVARIANTS}, "error": "", "self_test": {}}
        try:
            analysed = ResearchPaperPipeline().run(paper["pdf_path"]).paper
            row["violations"] = check_paper(analysed, paper.get("floors"), paper["title"])
            if not any(row["violations"].values()):
                row["self_test"] = self_test(analysed, paper.get("floors"), paper["title"])
        except Exception as error:  # a crash is reported against the paper, with the others still checked
            row["error"] = f"{type(error).__name__}: {error}"
            row["violations"]["references_extracted"].append(f"the pipeline failed on this paper: {row['error']}")
        row["ok"] = not any(row["violations"].values()) and bool(row["self_test"]) and all(row["self_test"].values())
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
    lines.append("licence verification is PENDING human confirmation: the licences were read from the arXiv abstract pages by an AI assistant, not by a human reviewer; the papers have no annotations, so only invariants are checked")
    return "\n".join(lines)
