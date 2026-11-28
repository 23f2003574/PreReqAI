"""Hybrid evidence retrieval for questions that name no concept: the lexical search PreReqAI already had, then BM25 with section-role weighting as a conservative fallback.

Both work on the same stored, quotable sentences (backend/evidence.quotable_sentences), so every passage either returns is an exact quotation of the page it cites and a model's
citations of it are checked exactly as before (backend/tutor/grounding.verify). `hybrid_search` returns the lexical passages unchanged and, only when they are fewer than
`MIN_LEXICAL`, adds BM25 passages (best first) that pass a conservative gate: they must match at least MIN_TERMS distinct query terms (one when the query has just one) and reach MIN_RELATIVE of
the best score. A question with no usable terms, or a paper with no quotable sentence, retrieves nothing. BM25 uses k1=1.5, b=0.75 over stemmed content terms; sentences in instructional sections
(Background, Method...) are weighted ROLE_WEIGHT["instructional"], related-work sentences less; the weights break ties and nudge, they never admit a sentence with no matching term."""
import math
import re
import weakref

from backend.evidence import passage_id, quotable_sentences
from backend.prerequisites.missing_prerequisite_analyzer import section_role

K1, B = 1.5, 0.75
ROLE_WEIGHT = {"instructional": 1.15, "other": 1.0, "related": 0.9}
MIN_TERMS, MIN_RELATIVE, MIN_LEXICAL = 2, 0.4, 2
RARE_SHARE, RARE_MIN_CHARS = 0.10, 4
RRF_K, POOL, BM25_WEIGHT = 60, 3, 1.0  # reciprocal-rank fusion constant, and how many times `limit` passages each search contributes to the fusion  # a single matching term is enough when it occurs in at most this share of the paper's sentences (and has at least RARE_MIN_CHARS letters)


_COMPOUND = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
_MIXED = re.compile(r"(?<![a-z0-9])(?=[a-z]*\d)(?=\d*[a-z])[a-z0-9]{2,}(?![a-z0-9])")


def _tokens(text):
    """The stemmed content terms of a text for BM25. Beyond the shared `_terms`: the parts of a hyphenated compound are terms too ("grade-school" also gives "grade" and "school", so a question that
    writes the words apart still matches the paper's compound and the reverse), and a token that mixes letters and digits ("13b", "t5", "k2") is a term, which `_terms` drops with every number."""
    from backend.session.context_retriever import _GENERIC, _stem, _terms

    lower = text.lower()
    terms = _terms(text)
    for compound in _COMPOUND.findall(lower):
        terms.extend(_stem(part) for part in compound.split("-") if len(part) > 2 and part not in _GENERIC and not part.isdigit())
    terms.extend(_MIXED.findall(lower))
    return terms


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


_INDEXES = {}  # id(paper) -> (weak reference to the paper, index); a paper is not hashable, so it is keyed by identity and the entry goes when the paper does


def _index(paper):
    """What BM25 needs from a paper and a question never changes: the quotable sentences, their stemmed terms, the set of terms of each, the average length and how many sentences contain each term. It is built
    once per paper (kept while the paper object lives and its paragraphs and pages are the same) instead of for every question; the result of a search is identical to rebuilding it each time."""
    marker = (id(getattr(paper, "paragraphs", None)), len(getattr(paper, "paragraphs", None) or []), id(getattr(paper, "pages", None)), len(getattr(paper, "pages", None) or []))
    held = _INDEXES.get(id(paper))
    cached = held[1] if held is not None and held[0]() is paper else None
    if cached is not None and cached["marker"] == marker:
        return cached
    candidates = quotable_sentences(paper)
    docs = [_tokens(sentence) for _, _, _, _, sentence, _ in candidates]
    sets = [set(doc) for doc in docs]
    frequency = {}
    for terms in sets:
        for term in terms:
            frequency[term] = frequency.get(term, 0) + 1
    built = {"marker": marker, "candidates": candidates, "docs": docs, "sets": sets, "frequency": frequency, "average": (sum(len(d) for d in docs) / len(docs)) if docs else 1.0}
    built["average"] = built["average"] or 1.0
    try:
        _INDEXES[id(paper)] = (weakref.ref(paper), built)
        weakref.finalize(paper, _INDEXES.pop, id(paper), None)
    except TypeError:  # an object that cannot be weakly referenced is simply indexed every time
        _INDEXES.pop(id(paper), None)
    return built


def bm25_search(paper, question, limit=5):
    """Passages ranked by BM25 with role weighting (the same dictionaries as evidence.build_evidence), best first; [] when nothing passes the gate."""
    from backend.tutor.grounding import named_concepts

    query = _query(paper, question)
    index = _index(paper)
    candidates = index["candidates"]
    if not query or not candidates:
        return []
    docs, sets, frequency, total, average = index["docs"], index["sets"], index["frequency"], len(index["docs"]), index["average"]
    scored = []
    for position, (doc, terms, (_, _, _, section, sentence, number)) in enumerate(zip(docs, sets, candidates)):
        matched = [term for term in query if term in terms]
        if not matched or (len(matched) < MIN_TERMS and len(query) >= MIN_TERMS and not (len(matched[0]) >= RARE_MIN_CHARS and frequency.get(matched[0], 0) <= RARE_SHARE * total)):
            continue
        score = 0.0
        for term in matched:
            df = frequency[term]
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            count = doc.count(term)
            score += idf * count * (K1 + 1) / (count + K1 * (1 - B + B * len(doc) / average))
        scored.append((-(score * ROLE_WEIGHT[section_role(section)]), position, section, sentence, number))
    if not scored:
        return []
    scored.sort(key=lambda item: item[:2])
    best = -scored[0][0]
    names = [c.name for c in getattr(paper, "concepts", []) or []]
    return [{"passage_id": passage_id(section, sentence), "sentence": sentence, "page_number": number, "section": section, "concepts": named_concepts(names, sentence)}
            for score, _, section, sentence, number in scored[:limit] if -score >= MIN_RELATIVE * best]


CONTEXT_TOP = 2  # the best passages whose next sentence is offered as context


def _with_context(paper, found, limit):
    """`found` followed, while there is room under `limit`, by the sentence after each of the first CONTEXT_TOP passages (then the one before): a question's answer often sits in the sentence next to the one that
    shares its words. They come after every ranked passage, never displace one, and are exact stored sentences with their own page, so quotations stay verbatim."""
    from backend.tutor.grounding import named_concepts

    candidates = quotable_sentences(paper)
    position = {passage_id(c[3], c[4]): i for i, c in enumerate(candidates)}
    names = [c.name for c in getattr(paper, "concepts", []) or []]
    result, seen = list(found), {p["passage_id"] for p in found}
    for passage in found[:CONTEXT_TOP]:
        at = position.get(passage["passage_id"])
        for neighbour in () if at is None else (at + 1, at - 1):
            if 0 <= neighbour < len(candidates) and len(result) < limit:
                _, _, _, section, sentence, number = candidates[neighbour]
                identifier = passage_id(section, sentence)
                if identifier not in seen:
                    seen.add(identifier)
                    result.append({"passage_id": identifier, "sentence": sentence, "page_number": number, "section": section, "concepts": named_concepts(names, sentence), "context": True})
    return result


def hybrid_search(paper, question, limit=4):
    """Lexical and BM25 passages fused by reciprocal rank (score 1 / (RRF_K + rank) summed over the lists a passage is in; the lexical list is the paper's own evidence search, BM25 the weighted statistical one), best
    first, none repeated, then the neighbouring sentence of the best ones as context while room is left; at most `limit`. Both searches always run: a passage that both find rises above one only a single search finds, and a
    question the lexical search answers badly (a single decisive rare term such as "beta") is no longer left to it. Every passage is still an exact quotation of the page it cites."""
    from backend.tutor.grounding import search_evidence

    lexical = list(search_evidence(paper, question, limit * POOL))
    statistical = bm25_search(paper, question, limit * POOL)
    scores, passages = {}, {}
    for weight, ranking in ((1.0, lexical), (BM25_WEIGHT, statistical)):
        for rank, passage in enumerate(ranking, start=1):
            identifier = passage["passage_id"]
            scores[identifier] = scores.get(identifier, 0.0) + weight / (RRF_K + rank)
            passages.setdefault(identifier, passage)
    order = sorted(scores, key=lambda identifier: -scores[identifier])  # stable: ties keep the lexical-first insertion order
    found = [passages[identifier] for identifier in order[:limit]]
    return _with_context(paper, found, limit) if found else found
