"""Hybrid evidence retrieval for questions that name no concept: the lexical search PreReqAI already had, then BM25 with section-role weighting as a conservative fallback.

Both work on the same stored, quotable sentences (backend/evidence.quotable_sentences), so every passage either returns is an exact quotation of the page it cites and a model's
citations of it are checked exactly as before (backend/tutor/grounding.verify). `hybrid_search` returns the lexical passages unchanged and, only when they are fewer than
`MIN_LEXICAL`, adds BM25 passages (best first) that pass a conservative gate: they must match at least MIN_TERMS distinct query terms (one when the query has just one) and reach MIN_RELATIVE of
the best score. A question with no usable terms, or a paper with no quotable sentence, retrieves nothing. BM25 uses k1=1.5, b=0.75 over stemmed content terms; sentences in instructional sections
(Background, Method...) are weighted ROLE_WEIGHT["instructional"], related-work sentences less; the weights break ties and nudge, they never admit a sentence with no matching term."""
import math
import re

from backend.evidence import passage_id, quotable_sentences
from backend.prerequisites.missing_prerequisite_analyzer import section_role

K1, B = 1.5, 0.75
ROLE_WEIGHT = {"instructional": 1.15, "other": 1.0, "related": 0.9}
MIN_TERMS, MIN_RELATIVE, MIN_LEXICAL = 2, 0.5, 2


def _tokens(text):
    from backend.session.context_retriever import _terms

    return _terms(text)


def _query(paper, question):
    from backend.concepts.concept_registry import ConceptRegistry
    from backend.session.context_retriever import _stem
    from backend.tutor.grounding import _acronyms, _pattern

    registry = {c.name: c for c in ConceptRegistry(custom=True).all()}
    query = set(_tokens(question)) | {_stem(term) for term in _acronyms(question)}
    for name, concept in registry.items():
        if _pattern(concept).search(question):
            query |= set(_tokens(name))
    return query


def bm25_search(paper, question, limit=5):
    """Passages ranked by BM25 with role weighting (the same dictionaries as evidence.build_evidence), best first; [] when nothing passes the gate."""
    from backend.tutor.grounding import named_concepts

    candidates, query = quotable_sentences(paper), None
    query = _query(paper, question)
    if not query or not candidates:
        return []
    docs = [_tokens(sentence) for _, _, _, _, sentence, _ in candidates]
    total, average = len(docs), (sum(len(d) for d in docs) / len(docs)) or 1.0
    frequency = {term: sum(term in set(doc) for doc in docs) for term in query}
    scored = []
    for index, (doc, (_, _, _, section, sentence, number)) in enumerate(zip(docs, candidates)):
        matched = [term for term in query if term in set(doc)]
        if not matched or (len(matched) < MIN_TERMS and len(query) >= MIN_TERMS):
            continue
        score = 0.0
        for term in matched:
            idf = math.log(1 + (total - frequency[term] + 0.5) / (frequency[term] + 0.5))
            count = doc.count(term)
            score += idf * count * (K1 + 1) / (count + K1 * (1 - B + B * len(doc) / average))
        scored.append((-(score * ROLE_WEIGHT[section_role(section)]), index, section, sentence, number))
    if not scored:
        return []
    scored.sort(key=lambda item: item[:2])
    best = -scored[0][0]
    names = [c.name for c in getattr(paper, "concepts", []) or []]
    return [{"passage_id": passage_id(section, sentence), "sentence": sentence, "page_number": number, "section": section, "concepts": named_concepts(names, sentence)}
            for score, _, section, sentence, number in scored[:limit] if -score >= MIN_RELATIVE * best]


def hybrid_search(paper, question, limit=4):
    """The lexical passages, and BM25 passages added when the lexical search found fewer than MIN_LEXICAL; at most `limit`, none repeated."""
    from backend.tutor.grounding import search_evidence

    found = list(search_evidence(paper, question, limit))
    if len(found) < MIN_LEXICAL:
        seen = {p["passage_id"] for p in found}
        for passage in bm25_search(paper, question, limit):
            if passage["passage_id"] not in seen and len(found) < limit:
                seen.add(passage["passage_id"])
                found.append(passage)
    return found
