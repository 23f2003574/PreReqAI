"""A prerequisite reading list from the paper's own citations: the cited works worth reading first, why, and which concepts they support.

Everything comes from the paper: how often a reference is cited in the text (the bibliography itself is not counted), in which sections (a citation in
the Introduction or Background counts most, in Method or another instructional section next, in Related Work, Experiments or elsewhere least), and which
detected concepts the citing sentences mention. Titles, authors and years are those the reference parser found, and an identifier (arXiv id or DOI) is only
one that appears in the reference text; a reference without one is listed as unresolved, with its text as written, and nothing is looked up or guessed. Nothing
is downloaded here: the list carries a `source` (the arXiv id or DOI) the learner can send to the analyze endpoint to read that paper next."""
import re

from backend.concepts.concept_registry import ConceptRegistry
from backend.evidence import _pattern
from backend.sentences import split_sentences
from backend.ingestion.research_source_detector import ARXIV_ID_PATTERN, ARXIV_PATTERN, DOI_PATTERN
from backend.parsing.citation_extractor import CITATION_PATTERN, reference_numbers
from backend.prerequisites.missing_prerequisite_analyzer import section_role

_FOUNDATION = ("introduction", "background", "preliminar", "notation", "motivation", "overview", "problem")
_NUMBERING = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[ivx]+\.)\s*")
MAX_ITEMS = 10
WEIGHT_FOUNDATION, WEIGHT_INSTRUCTIONAL, WEIGHT_OTHER = 3.0, 2.0, 1.0


def section_weight(title):
    """How much one citation in this section says that the work is foundational."""
    name = " ".join((title or "").lower().split())
    name = _NUMBERING.sub("", name)
    if name.startswith(_FOUNDATION):
        return WEIGHT_FOUNDATION
    return WEIGHT_INSTRUCTIONAL if section_role(title) == "instructional" else WEIGHT_OTHER


def identifiers(text):
    """(arXiv id or None, DOI or None) written in a reference's text."""
    arxiv = ARXIV_PATTERN.search(text) or ARXIV_ID_PATTERN.search(text)
    doi = DOI_PATTERN.search(text)
    return (arxiv.group(1) if arxiv else None, doi.group(1).rstrip(".,;)") if doi else None)


def build_reading_list(paper, limit=MAX_ITEMS):
    """[{rank, reference_number, title, authors, year, reference, arxiv_id, doi, source, status, score, citations, sections, concepts, reason}]: the cited works
    most worth reading first, most important first (ties by more supported concepts, then reference number: the order is deterministic). `status` is "resolvable" (an
    identifier is in the reference) or "unresolved". A paper without citations or references gives []."""
    references = {item.reference_number: item.raw_text for item in getattr(paper, "references", []) or []}
    related = {item.reference_number: item for item in getattr(paper, "related_papers", []) or []}
    registry = {c.name: c for c in ConceptRegistry().all()}
    detected = [c.name for c in getattr(paper, "concepts", []) or [] if c.name in registry]
    cited = {}  # reference number -> {"score", "count", "sections": {title: n}, "concepts": {name: n}}
    for citation in getattr(paper, "citations", []) or []:
        if citation.reference_number not in references:
            continue  # a number the bibliography does not have is not a work that can be listed
        entry = cited.setdefault(citation.reference_number, {"score": 0.0, "count": 0, "sections": {}, "concepts": {}})
        entry["score"] += section_weight(citation.section)
        entry["count"] += 1
        title = (citation.section or "").strip() or "untitled section"
        entry["sections"][title] = entry["sections"].get(title, 0) + 1
        for sentence in split_sentences(citation.context or ""):  # the sentences of the citing paragraph that carry this very citation
            if any(citation.reference_number in reference_numbers(match.group(1)) for match in CITATION_PATTERN.finditer(sentence)):
                for name in detected:
                    if _pattern(registry[name]).search(sentence):
                        entry["concepts"][name] = entry["concepts"].get(name, 0) + 1
    ranked = sorted(cited.items(), key=lambda item: (-item[1]["score"], -len(item[1]["concepts"]), item[0]))
    result = []
    for rank, (number, entry) in enumerate(ranked[:limit], start=1):
        text = " ".join(references[number].split())
        arxiv_id, doi = identifiers(text)
        info = related.get(number)
        found = " and ".join(f"{count} in {title}" for title, count in sorted(entry["sections"].items(), key=lambda pair: (-pair[1], pair[0]))[:3])
        concepts = sorted(entry["concepts"], key=lambda name: (-entry["concepts"][name], name))
        result.append({
            "rank": rank, "reference_number": number, "title": (info.title if info and info.title and info.title != references[number] else None),
            "authors": list(info.authors) if info else [], "year": info.year if info else None, "reference": text[:400], "arxiv_id": arxiv_id, "doi": doi,
            "source": f"arXiv:{arxiv_id}" if arxiv_id else doi, "status": "resolvable" if (arxiv_id or doi) else "unresolved",
            "score": entry["score"], "citations": entry["count"], "sections": entry["sections"], "concepts": concepts,
            "reason": f"Cited {entry['count']} time{'s' if entry['count'] != 1 else ''} ({found})"
                      + (f"; the citing sentences mention {', '.join(concepts[:4])}." if concepts else "; no detected concept is named in the citing sentences.")
                      + ("" if arxiv_id or doi else " No arXiv id or DOI is written in the reference, so it cannot be opened from here."),
        })
    return result
