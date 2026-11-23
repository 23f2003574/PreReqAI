"""Retrieval on real papers: 36 questions with gold phrases over the six licensed PDFs (DPO, Mixtral, Chain-of-Thought, Constitutional AI, GQA, Mistral 7B).

`fixtures/retrieval_questions.json` says where the questions come from: written by the AI assistant that built this evaluation, gold phrases checked to occur in the papers, NOT reviewed by a human.
A returned passage is a HIT when its quotation contains the gold phrase (comparison ignores case, spaces and punctuation). For the lexical search (backend/tutor/grounding.search_evidence) and the
hybrid one (backend/retrieval.hybrid_search) the evaluation reports, per paper and overall, recall@K (a hit among the first K passages) and MRR (1 / rank of the first hit, 0 without one), the share of
questions whose gold phrase occurs in the extracted page text at all (`gold_in_text`: a question whose answer the extraction lost cannot be retrieved), and whether every returned passage is an exact
quotation of its page. The gate compares the two searches (hybrid must not do worse, every quotation exact, the question set must not shrink) and holds absolute floors for the hybrid search (overall recall@K
and MRR and recall@K per paper, thresholds.json), set from the measured numbers `--gate` prints. Offline and deterministic."""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
QUESTIONS = HERE / "fixtures" / "retrieval_questions.json"
K = 5
PDF_DIRS = (HERE / "benchmark" / "pdfs", HERE / "heldout" / "pdfs")


def key(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def load(path=QUESTIONS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "prereqai-retrieval-questions":
        raise ValueError(f"{path} is not a retrieval question set")
    return data


def pdf_paths(ids):
    """{paper id: PDF path} for the ids whose PDF is shipped."""
    found = {}
    for paper_id in ids:
        for directory in PDF_DIRS:
            if (directory / f"{paper_id}.pdf").is_file():
                found[paper_id] = str(directory / f"{paper_id}.pdf")
    return found


def rank_of(passages, gold):
    """1-based rank of the first passage whose quotation contains the gold phrase, or None."""
    wanted = key(gold)
    return next((n for n, passage in enumerate(passages, start=1) if wanted in key(passage["sentence"])), None)


def evaluate(papers, data=None, k=K, searches=None):
    """{"questions", "k", "systems": {name: {recall_at_k, mrr, quotations_verified, by_paper: {id: {questions, recall_at_k, mrr}}}}, "gold_in_text", "by_style", ...} for `papers` ({id: analysed
    paper}); questions of papers not given are left out. `searches` ({name: callable(paper, question, k)}) replaces the lexical and hybrid searches."""
    from backend.retrieval import hybrid_search
    from backend.tutor.grounding import search_evidence

    data = data or load()
    searches = searches or {"lexical": lambda paper, question, limit: search_evidence(paper, question, limit), "hybrid": lambda paper, question, limit: hybrid_search(paper, question, limit)}
    questions = [q for q in data["questions"] if q["paper"] in papers]
    text = {paper_id: key(" ".join(page.text for page in paper.pages)) for paper_id, paper in papers.items()}
    pages = {paper_id: {page.page_number: page.text for page in paper.pages} for paper_id, paper in papers.items()}
    systems = {}
    for name, search in searches.items():
        hits, reciprocal, quotes, passages_total, per = 0, 0.0, 0, 0, {}
        for q in questions:
            found = list(search(papers[q["paper"]], q["question"], k))[:k]
            rank = rank_of(found, q["gold"])
            row = per.setdefault(q["paper"], {"questions": 0, "hits": 0, "rr": 0.0})
            row["questions"] += 1
            row["hits"] += rank is not None
            row["rr"] += 1 / rank if rank else 0.0
            hits += rank is not None
            reciprocal += 1 / rank if rank else 0.0
            for passage in found:
                passages_total += 1
                quotes += passage["sentence"] in pages[q["paper"]].get(passage.get("page_number"), "")
        share = lambda a, b: a / b if b else 1.0
        systems[name] = {"recall_at_k": share(hits, len(questions)), "mrr": share(reciprocal, len(questions)), "quotations_verified": share(quotes, passages_total),
                         "by_paper": {pid: {"questions": r["questions"], "recall_at_k": round(r["hits"] / r["questions"], 3), "mrr": round(r["rr"] / r["questions"], 3)} for pid, r in sorted(per.items())}}
    styles = {}
    for q in questions:
        styles.setdefault(q["style"], []).append(q)
    return {"questions": len(questions), "k": k, "systems": systems, "gold_in_text": sum(key(q["gold"]) in text[q["paper"]] for q in questions) / len(questions) if questions else 1.0,
            "papers": sorted({q["paper"] for q in questions}), "styles": {s: len(v) for s, v in sorted(styles.items())}, "status": data["status"], "provenance": data["provenance"]}


FAILURE_CLASSES = ("evidence_absent", "tokenisation", "vocabulary_mismatch", "below_term_gate", "lexical_crowding", "context_outside", "ranking")


def classify_failures(papers, data=None, k=K, search=None):
    """[{id, paper, question, gold, class, detail}] for each question the search misses in the first `k` passages, with the first of these reasons that holds (reproducible: no model is involved):
    evidence_absent (the gold phrase is not in the extracted text), tokenisation (no query term meets the gold sentences under the shared `_terms` tokens, but one does under the retrieval tokens, so the
    tokens, not the wording, were the obstacle), vocabulary_mismatch (no query term occurs in any sentence with the gold phrase: the question and the paper use different words), below_term_gate (a
    gold sentence shares terms with the question but fewer than the gate needs), context_outside (a returned passage is next to a gold sentence: the answer sits just outside it), lexical_crowding (the
    lexical search returned enough passages that BM25 was never consulted), ranking (BM25 sees a gold sentence but ranks it below `k`)."""
    from backend import retrieval
    from backend.evidence import quotable_sentences
    from backend.session.context_retriever import _terms

    data = data or load()
    search = search or (lambda paper, question, limit: retrieval.hybrid_search(paper, question, limit))
    texts = {pid: key(" ".join(page.text for page in paper.pages)) for pid, paper in papers.items()}
    rows = []
    for q in data["questions"]:
        paper = papers.get(q["paper"])
        if paper is None:
            continue
        found = list(search(paper, q["question"], k))[:k]
        if rank_of(found, q["gold"]):
            continue
        sentences = [c[4] for c in quotable_sentences(paper)]
        gold_at = [i for i, sentence in enumerate(sentences) if key(q["gold"]) in key(sentence)]
        query = retrieval._query(paper, q["question"])
        shared = max((len(query & set(retrieval._tokens(sentences[i]))) for i in gold_at), default=0)
        old = set(_terms(q["question"]))
        shared_old = max((len(old & set(_terms(sentences[i]))) for i in gold_at), default=0)
        returned = {key(p["sentence"]) for p in found}
        next_to = any(key(sentences[j]) in returned for i in gold_at for j in (i - 1, i + 1) if 0 <= j < len(sentences))
        if key(q["gold"]) not in texts[q["paper"]] or not gold_at:
            kind, detail = "evidence_absent", "the gold phrase is not among the paper's quotable sentences"
        elif shared == 0:
            kind, detail = "vocabulary_mismatch", "no query term occurs in a sentence containing the gold phrase"
        elif shared_old == 0:
            kind, detail = "tokenisation", "only the retrieval tokens (hyphen parts, letter-digit terms) connect the question to the gold sentence"
        elif next_to:
            kind, detail = "context_outside", "a returned passage is adjacent to a gold sentence"
        elif shared < retrieval.MIN_TERMS and len(query) >= retrieval.MIN_TERMS:
            kind, detail = "below_term_gate", f"a gold sentence shares {shared} query term(s); the gate needs {retrieval.MIN_TERMS} unless the term is rare"
        elif len(found) >= retrieval.MIN_LEXICAL:
            kind, detail = "lexical_crowding", f"the lexical search returned {len(found)} passages, so BM25 was not consulted"
        else:
            kind, detail = "ranking", "BM25 sees a gold sentence but ranks other sentences first"
        rows.append({"id": q["id"], "paper": q["paper"], "question": q["question"], "gold": q["gold"], "class": kind, "detail": detail})
    return rows


def failure_summary(rows):
    """{class: count} over classify_failures rows, every class present."""
    return {kind: sum(r["class"] == kind for r in rows) for kind in FAILURE_CLASSES}
