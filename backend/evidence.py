"""Source-grounded evidence for detected concepts: the paper's own sentences that mention them, with where they are.

A passage is {passage_id, sentence, page_number, section, concepts}: `sentence` is copied verbatim from the paper (never paraphrased or trimmed), and a
sentence is kept only if it is an exact substring of the text of the page it cites; `page_number` is None for a session saved before pages were
recorded (the passage is then kept, without a page). `passage_id` is "p-" and ten hex digits of a hash of the section and the sentence, so it is stable
across runs and the same sentence has the same id for every concept it supports. A concept gets at most MAX_PER_CONCEPT passages, instructional
sections first, then paper order, and no sentence appears twice for a concept. The bibliography and acknowledgements are never quoted."""
import hashlib
import re
from functools import lru_cache

from backend.concepts.concept_registry import ConceptRegistry
from backend.concepts.rule_based_concept_detector import _BACK_MATTER
from backend.prerequisites.missing_prerequisite_analyzer import section_role

MAX_PER_CONCEPT = 3
MIN_SENTENCE_CHARS, MAX_SENTENCE_CHARS = 30, 400
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[“\"])")
_ROLE_RANK = {"instructional": 0, "other": 1, "related": 2}


@lru_cache(maxsize=None)
def _pattern(concept):
    """One compiled alternation of a concept's name and aliases: whole words, a plural, a hyphen or a space between words."""
    terms = sorted({concept.name, *concept.aliases}, key=len, reverse=True)
    body = "|".join(r"[\s\-]+".join(re.escape(word) for word in re.split(r"[\s\-]+", term)) + r"s?" for term in terms)
    return re.compile(rf"(?<![A-Za-z0-9])(?:{body})(?![A-Za-z0-9])", re.IGNORECASE)


def passage_id(section, sentence):
    return "p-" + hashlib.sha1(f"{section}\n{sentence}".encode("utf-8")).hexdigest()[:10]


def _page_of(pages, number, sentence):
    """The page that really holds `sentence` (the paragraph's page or the next one, for a paragraph that crosses a page break), else None."""
    for candidate in (number, number + 1):
        if sentence in pages.get(candidate, ""):
            return candidate
    return None


def build_evidence(paper, limit=MAX_PER_CONCEPT):
    """{concept name: [passage, ...]} for the paper's detected concepts that have at least one quotable sentence, strongest first."""
    concepts = list(getattr(paper, "concepts", []) or [])
    registry = {c.name: c for c in ConceptRegistry().all()}
    pages = {page.page_number: page.text for page in getattr(paper, "pages", []) or []}
    candidates = []  # (role rank, paragraph order, sentence order, section, sentence, page)
    for order, paragraph in enumerate(getattr(paper, "paragraphs", []) or []):
        section = (paragraph.section_title or "").strip()
        if _BACK_MATTER.match(section):
            continue
        for position, sentence in enumerate(_SENTENCES.split((paragraph.content or "").strip())):
            if not MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS:
                continue
            number = getattr(paragraph, "page_number", None)
            if number is not None and pages:
                number = _page_of(pages, number, sentence)
                if number is None:
                    continue  # it is not in the page it would cite: never quote it as if it were
            candidates.append((_ROLE_RANK[section_role(section)], order, position, section, sentence, number))
    candidates.sort(key=lambda item: item[:3])
    result = {}
    for concept in concepts:
        entry = registry.get(concept.name)
        if entry is None:
            continue
        pattern, seen, passages = _pattern(entry), set(), []
        for _, _, _, section, sentence, number in candidates:
            key = " ".join(sentence.split()).casefold()
            if key in seen or not pattern.search(sentence):
                continue
            seen.add(key)
            mentioned = [c.name for c in concepts if c.name in registry and _pattern(registry[c.name]).search(sentence)]
            passages.append({"passage_id": passage_id(section, sentence), "sentence": sentence, "page_number": number, "section": section,
                             "concepts": mentioned})
            if len(passages) == limit:
                break
        if passages:
            result[concept.name] = passages
    return result
