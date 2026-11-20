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
MAX_RESIDUE, MIN_LETTERS = 0.35, 25  # a candidate that is more than 35% numeric tokens or symbols, or has under 25 letters, is chart or table residue
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[“\"])")
_ROLE_RANK = {"instructional": 0, "other": 1, "related": 2}
_TRAILING_PAGE_NUMBER = re.compile(r"(?<=[.!?])\s*\n\s*\d{1,3}\s*$")  # "... in the model.\n6": the page number that follows the last sentence of a page
_DEFINITION = re.compile(r"\b(?:is|are|was|refers? to|denotes?|defined? as|is defined|called|known as|consists? of|we (?:propose|introduce|use|define|present|apply)|allows?|enables?|instead of)\b", re.I)
_CAPTION = re.compile(r"^(?:fig(?:ure)?|table|algorithm|listing)\.?\s*\d+", re.I)


def residue_share(sentence):
    """How much of a 'sentence' is chart or table residue (axis ticks, numbers, one-word lines) rather than prose: the larger of the share of numeric tokens and of
    characters that are not letters or spaces, and 1.0 for text made of many short lines."""
    tokens = sentence.split()
    if not tokens:
        return 1.0
    numeric = sum(1 for token in tokens if re.fullmatch(r"[-+\u2212]?[\d.,%/()]+|[\d.]+[a-zA-Z]?", token)) / len(tokens)
    visible = [c for c in sentence if not c.isspace()]
    symbols = sum(1 for c in visible if not c.isalpha()) / max(1, len(visible))
    lines = [line for line in sentence.split("\n") if line.strip()]
    short = len(lines) >= 5 and sum(len(line.split()) <= 2 for line in lines) / len(lines) > 0.6
    return 1.0 if short else max(numeric, symbols * 0.8)


def usefulness(sentence, section, concept_terms):
    """A score for ranking the sentences that mention a concept: a definitional or methodological verb, the concept early in the sentence and not just once in a list, a
    sentence of prose length, in an instructional section; captions and sentences full of symbols score lower."""
    words = sentence.split()
    score = 2.0 if _DEFINITION.search(sentence) else 0.0
    first = concept_terms.search(sentence)
    if first:
        score += 1.0 if first.start() < max(40, len(sentence) // 3) else 0.0
        score += min(2, len(concept_terms.findall(sentence)) - 1) * 0.5
    score += 1.0 if 8 <= len(words) <= 45 else -1.0
    score += {0: 1.5, 1: 0.5, 2: -0.5}[_ROLE_RANK[section_role(section)]]
    bare = re.sub(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s*", "", section.strip()).lower()
    score += 1.0 if bare.startswith(("abstract", "introduction", "preliminar", "background", "method", "approach", "model")) else 0.0
    score -= 1.5 if re.match(r"^(?:appendix\b|[A-Z](?:\.\d+)*\s+\S)", section.strip()) else 0.0  # an appendix: implementation detail rather than where the concept is introduced
    score -= 1.5 if _CAPTION.match(sentence) else 0.0
    score -= 3.0 * residue_share(sentence)
    score -= 0.3 * max(0, sentence.count("\n") - 3)
    return score


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


def quotable_sentences(paper):
    """[(role rank, paragraph order, sentence order, section, sentence, page)] for every sentence of the paper that may be quoted (body sections only, residue removed, each one an exact
    part of the text of the page it cites), in paper order."""
    pages = {page.page_number: page.text for page in getattr(paper, "pages", []) or []}
    candidates = []  # (role rank, paragraph order, sentence order, section, sentence, page)
    for order, paragraph in enumerate(getattr(paper, "paragraphs", []) or []):
        section = (paragraph.section_title or "").strip()
        if _BACK_MATTER.match(section):
            continue
        for position, sentence in enumerate(_SENTENCES.split((paragraph.content or "").strip())):
            sentence = _TRAILING_PAGE_NUMBER.sub("", sentence).strip()  # a prefix of the page text, so still an exact quotation
            if not MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS or residue_share(sentence) > MAX_RESIDUE or sum(c.isalpha() for c in sentence) < MIN_LETTERS:
                continue
            number = getattr(paragraph, "page_number", None)
            if number is not None and pages:
                number = _page_of(pages, number, sentence)
                if number is None:
                    continue  # it is not in the page it would cite: never quote it as if it were
            candidates.append((_ROLE_RANK[section_role(section)], order, position, section, sentence, number))
    candidates.sort(key=lambda item: item[:3])
    return candidates


def build_evidence(paper, limit=MAX_PER_CONCEPT):
    """{concept name: [passage, ...]} for the paper's detected concepts that have at least one quotable sentence, strongest first."""
    concepts = list(getattr(paper, "concepts", []) or [])
    registry = {c.name: c for c in ConceptRegistry().all()}
    pages = {page.page_number: page.text for page in getattr(paper, "pages", []) or []}
    candidates = quotable_sentences(paper)
    candidates.sort(key=lambda item: item[:3])  # paper order; the ranking per concept below decides which of them are shown
    result = {}
    for concept in concepts:
        entry = registry.get(concept.name)
        if entry is None:
            continue
        pattern, seen, ranked = _pattern(entry), set(), []
        for order, (_, _, _, section, sentence, number) in enumerate(candidates):
            key = " ".join(sentence.split()).casefold()
            if key in seen or not pattern.search(sentence):
                continue
            seen.add(key)
            ranked.append((-usefulness(sentence, section, pattern), order, section, sentence, number))
        ranked.sort(key=lambda item: item[:2])  # most useful first; equal scores keep paper order, so the result is deterministic
        passages = []
        for _, _, section, sentence, number in ranked[:limit]:
            mentioned = [c.name for c in concepts if c.name in registry and _pattern(registry[c.name]).search(sentence)]
            passages.append({"passage_id": passage_id(section, sentence), "sentence": sentence, "page_number": number, "section": section, "concepts": mentioned})
        if passages:
            result[concept.name] = passages
    return result
