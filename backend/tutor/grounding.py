"""Deterministic grounding checks for a model-written tutor answer: the answer must cite the evidence passages it was given, every cited passage id
and quotation must match the stored passage exactly, and no number in the answer may come from nowhere. Nothing here calls a model; a citation is
never trusted because the model supplied it."""
import json
import re

import math

from backend.concepts.concept_registry import ConceptRegistry
from backend.evidence import _pattern, build_evidence, passage_id, quotable_sentences

from .tutor_provider import ProviderError

MAX_EVIDENCE, PER_CONCEPT = 6, 2
MIN_QUOTE_CHARS, MAX_CITATIONS = 12, 6
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
_SPACES = re.compile(r"\s+")


def _norm(text):
    return _SPACES.sub(" ", str(text)).strip()


MIN_COVERAGE, MAX_SEARCH = 0.4, 4


def _acronyms(question):
    return [word.lower() for word in re.findall(r"\b[A-Z]{2,6}s?\b", question)]  # "KL", "DPO": short, but they are the topic


def _bag(text):
    from backend.session.context_retriever import _stem

    return {_stem(word) for word in re.findall(r"[a-z][a-z\-]+", text.lower())}


def named_concepts(paper_concepts, question):
    """The detected concepts a question names, by the concept's name or any alias ("What is DPO?" names Direct Preference Optimization), in the paper's order."""
    registry = {c.name: c for c in ConceptRegistry().all()}
    return [name for name in paper_concepts if name in registry and _pattern(registry[name]).search(question)]


def search_evidence(paper, question, limit=MAX_SEARCH):
    """Quotable sentences (see evidence.quotable_sentences) that answer a question without naming a concept, found by their words: the question's content terms (and the
    spelled-out names of the concepts it names by an acronym) weighted by how rare they are in the paper; a sentence needs at least MIN_COVERAGE of that weight and a term that
    is not everywhere. Best first, ties in paper order. Returns the same passage dictionaries as build_evidence, so a model's citations of them are checked the same way."""
    from backend.session.context_retriever import _stem, _terms

    registry = {c.name: c for c in ConceptRegistry().all()}
    named = [name for name, concept in registry.items() if _pattern(concept).search(question)]
    query = {_stem(term) for term in [*_terms(question), *_acronyms(question)]}
    for name in named:
        query |= {_stem(term) for term in _terms(name)}
    candidates = quotable_sentences(paper)
    if not query or not candidates:
        return []
    bags = [_bag(sentence) for _, _, _, _, sentence, _ in candidates]
    total = len(bags)
    frequency = {term: sum(term in bag for bag in bags) for term in query}
    spelled = {_stem(term) for term in _acronyms(question)}
    weight = {term: (math.log((total + 1) / (frequency[term] + 0.5)) + 1) * (2.5 if term in spelled else 1.0) for term in query}  # an acronym is the topic
    whole, scored = sum(weight.values()), []
    for index, ((_, _, _, section, sentence, number), bag) in enumerate(zip(candidates, bags)):
        matched = query & bag
        coverage = sum(weight[term] for term in matched) / whole
        if coverage >= MIN_COVERAGE and any(frequency[term] <= max(1, total / 4) for term in matched):
            scored.append((-coverage, index, section, sentence, number))
    scored.sort(key=lambda item: item[:2])
    result = []
    for _, _, section, sentence, number in scored[:limit]:
        result.append({"passage_id": passage_id(section, sentence), "sentence": sentence, "page_number": number, "section": section, "concepts": named_concepts(
            [c.name for c in getattr(paper, "concepts", []) or []], sentence)})
    return result


def select_evidence(paper, concept_names, question=None):
    """The evidence passages (see backend.evidence) for a question: for the concepts it names at most PER_CONCEPT each and, when it names none or they have too little, sentences
    found by their words (search_evidence); MAX_EVIDENCE in all, none repeated. Every passage is a stored, verifiable quotation."""
    found = build_evidence(paper, limit=PER_CONCEPT)
    chosen, seen = [], set()

    def add(passages):
        for passage in passages:
            if passage["passage_id"] not in seen and len(chosen) < MAX_EVIDENCE:
                seen.add(passage["passage_id"])
                chosen.append(passage)

    for name in dict.fromkeys(concept_names):
        add(found.get(name, []))
    if question and len(chosen) < 2:
        add(search_evidence(paper, question))
    return chosen


def verify(raw, answer, evidence, known_text=""):
    """The verified citations of a model reply, [{passage_id, quote, sentence, page_number, section}] taken from the stored passages, or
    ProviderError("ungrounded", why). Checks, in order: a non-empty citation list; every passage id is one that was supplied; every quotation (at
    least MIN_QUOTE_CHARS characters, whitespace ignored) is a verbatim part of that stored passage; every number of the answer appears in a cited
    passage or in `known_text` (the question and the facts supplied)."""
    try:
        data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))
    except ValueError:
        raise ProviderError("ungrounded", "the reply could not be checked against the paper.") from None
    claimed = data.get("citations") if isinstance(data, dict) else None
    if not isinstance(claimed, list) or not claimed:
        raise ProviderError("ungrounded", "the answer cites no passage of the paper.")
    stored = {passage["passage_id"]: passage for passage in evidence}
    verified, seen = [], set()
    for item in claimed[:MAX_CITATIONS * 2]:
        identifier, quote = (item.get("passage_id"), item.get("quote")) if isinstance(item, dict) else (None, None)
        if not isinstance(identifier, str) or identifier not in stored:
            raise ProviderError("ungrounded", f"the answer cites a passage that was not supplied ({str(identifier)[:30]!r}).")
        if not isinstance(quote, str) or len(_norm(quote)) < MIN_QUOTE_CHARS or _norm(quote) not in _norm(stored[identifier]["sentence"]):
            raise ProviderError("ungrounded", f"a quotation attributed to passage {identifier} is not in that passage.")
        if (identifier, _norm(quote)) not in seen:
            seen.add((identifier, _norm(quote)))
            passage = stored[identifier]
            verified.append({"passage_id": identifier, "quote": _norm(quote), "sentence": passage["sentence"], "page_number": passage["page_number"],
                             "section": passage["section"]})
    support = _norm(" ".join([known_text, *(c["sentence"] for c in verified)]))
    for number in _NUMBER.findall(answer):
        if not re.search(rf"(?<![\w.]){re.escape(number)}(?![\w]|[.,]\d)", support):
            raise ProviderError("ungrounded", f"the answer states {number}, which no cited passage supports.")
    return verified[:MAX_CITATIONS]
