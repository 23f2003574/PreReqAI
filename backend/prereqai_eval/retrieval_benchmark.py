"""A question-to-passage retrieval benchmark made from the evidence PreReqAI already verified, and the measure of the lexical search against the hybrid (lexical plus BM25).

For each of a paper's top evidence passages (one per concept, at most MAX_PER_PAPER) a question is written from the passage's own distinctive words: its QUESTION_TERMS rarest content words
in the paper, leaving out the words of the concept's own name, as "What does the paper say about w1, w2, w3?". The gold answer is that passage. The questions are deterministic, name no concept
(that is the case the search has to solve) and depend on the paper's text only, so the same paper always gives the same benchmark. `recall_at_k` is the share of questions whose gold passage is
among the first k passages returned; `quotations_verified` the share of every returned passage that is an exact quotation of the page it cites (it must stay 1.0). Results are measured on whatever
papers are given: no number is stored here."""
import re

K = 5
MAX_PER_PAPER, QUESTION_TERMS, NOISE_TERMS, LOOSE_TERMS = 12, 3, 2, 4


def make_questions(paper):
    """[{question, gold, concept}] for an analysed paper."""
    from backend.concepts.concept_registry import ConceptRegistry
    from backend.evidence import build_evidence, quotable_sentences
    from backend.session.context_retriever import _terms

    candidates = [sentence for *_, sentence, _ in quotable_sentences(paper)]
    document = {}
    for sentence in candidates:
        for term in set(_terms(sentence)):
            document[term] = document.get(term, 0) + 1
    aliases = {c.name: c for c in ConceptRegistry(custom=True).all()}
    named = {t for c in aliases.values() for term in (c.name, *c.aliases) for t in _terms(term)}  # no question may name a concept, whichever concept it is
    questions = []
    for name, passages in build_evidence(paper).items():
        if len(questions) >= MAX_PER_PAPER or name not in aliases:
            continue
        own = {t for term in (name, *aliases[name].aliases) for t in _terms(term)}
        words = sorted({t for t in _terms(passages[0]["sentence"]) if t not in own and len(t) >= 5 and document.get(t, 0) >= 1}, key=lambda t: (document[t], t))[:QUESTION_TERMS]
        if len(words) >= 2:
            questions.append({"question": "What does the paper say about " + ", ".join(words[:-1]) + " and " + words[-1] + "?", "gold": passages[0]["passage_id"], "concept": name, "style": "clean"})
            inside = {t for t in _terms(passages[0]["sentence"])}
            others = sorted({t for sentence in candidates if sentence != passages[0]["sentence"] for t in _terms(sentence) if t not in inside and t not in own and t not in named and len(t) >= 5},
                            key=lambda t: (-document.get(t, 0), t))
            for style, count in (("noisy", NOISE_TERMS), ("loose", LOOSE_TERMS)):
                if len(others) >= count:
                    questions.append({"question": "What does the paper say about " + ", ".join(words[:2]) + ", " + " and ".join(others[:count]) + "?", "gold": passages[0]["passage_id"], "concept": name, "style": style})
    return questions


def _verified(paper, passage):
    pages = {p.page_number: " ".join(p.text.split()) for p in paper.pages}
    return passage["page_number"] in pages and " ".join(passage["sentence"].split()) in pages[passage["page_number"]]


def evaluate(papers, searches=None, k=K):
    """{"questions", "systems": {name: {"recall_at_k", "quotations_verified", "answered"}}} over analysed papers. `searches` is {name: function(paper, question, limit)}; by default the
    lexical search and the hybrid one."""
    from backend.retrieval import hybrid_search
    from backend.tutor.grounding import search_evidence

    searches = searches or {"lexical": search_evidence, "hybrid": hybrid_search}
    total, hits, verified, returned, answered = 0, dict.fromkeys(searches, 0), dict.fromkeys(searches, 0), dict.fromkeys(searches, 0), dict.fromkeys(searches, 0)
    styles, style_hits = {}, {name: {} for name in searches}
    for paper in papers:
        for item in make_questions(paper):
            total += 1
            styles[item["style"]] = styles.get(item["style"], 0) + 1
            for name, search in searches.items():
                found = search(paper, item["question"], k)
                hit = item["gold"] in [p["passage_id"] for p in found[:k]]
                answered[name] += bool(found)
                hits[name] += hit
                style_hits[name][item["style"]] = style_hits[name].get(item["style"], 0) + hit
                returned[name] += len(found)
                verified[name] += sum(_verified(paper, p) for p in found)
    return {"questions": total, "k": k, "styles": styles,
            "systems": {name: {"recall_at_k": hits[name] / total if total else 0.0, "quotations_verified": verified[name] / returned[name] if returned[name] else 1.0, "answered": answered[name],
                               "recall_by_style": {style: style_hits[name].get(style, 0) / count for style, count in styles.items()}} for name in searches}}
