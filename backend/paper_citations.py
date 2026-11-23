"""Which of the analysed papers cite each other, found conservatively from their reference lists.

A paper A cites an uploaded paper B when one of A's bibliography entries contains B's full title: at least MIN_TITLE_WORDS words and MIN_TITLE_CHARS characters once lower-cased and stripped of punctuation,
so a title like "Attention" can never match. Each link names the reference number and the entry's text. A reference whose text contains the titles of two or more different uploaded papers is
AMBIGUOUS and is listed, not used; a paper whose title is too short to match safely is listed as unmatchable; a paper citing itself is ignored. Links that form a cycle (A cites B and B cites A,
which a revised edition can do) are reported and not used for ordering. Nothing is downloaded or guessed.

A reference is matched by the first of these that finds exactly one analysed paper (the link says which, as `method`): "doi" (the reference contains the DOI printed in the paper), "arxiv_id" (it
contains the paper's arXiv identifier, version ignored, as "arXiv:1706.03762", "arxiv.org/abs/1706.03762", "arxiv.org/pdf/1706.03762.pdf" or the DOI form "10.48550/arXiv.1706.03762"), "title" (above) and "author_year_title" (it names the paper's first author's surname, a year within one of the paper's, and at least
MIN_TITLE_SHARE of the paper's content words of its title, four of them at least: for a reference that abbreviates or rewords the title). A method that finds two or more papers makes the reference
AMBIGUOUS: it is listed and never used, and no later method is tried. A paper is "unmatchable" only when it has neither a usable title nor an identifier."""
import re

MIN_TITLE_WORDS, MIN_TITLE_CHARS = 3, 15
MIN_TITLE_SHARE, MIN_CONTENT_WORDS = 0.6, 4
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
_ARXIV = re.compile(r"(?<![a-z])arxiv(?:\.org)?(?:\s*[:/.,]\s*|\s+)(?:(?:abs|pdf|e-print)/)?([0-9]{4}\.[0-9]{4,5}|[a-z\-]+(?:\.[a-z]{2})?/[0-9]{7})(?![0-9])(?:v[0-9]+)?", re.IGNORECASE)
_STOP = frozenset("a an the of and or in on for to with by from as at is are via using use based into over under towards toward".split())


def _doi(text):
    return {m.group(1).rstrip(".,;)]}").lower() for m in _DOI.finditer(str(text))}


def _arxiv(text):
    return {m.group(1).lower() for m in _ARXIV.finditer(str(text))}


def identifiers(session):
    """{"doi": set, "arxiv": set, "year": int or None, "surname": str} of an analysed paper, read from the first two pages (its arXiv stamp, a printed DOI) and its metadata; empty when unknown."""
    paper = getattr(session, "paper", None)
    text = " ".join(str(getattr(page, "text", "")) for page in (getattr(paper, "pages", None) or [])[:2])
    arxiv, doi = _arxiv(text), _doi(text)
    years = [int(a[:2]) + 2000 for a in arxiv if re.match(r"[0-9]{4}\.", a)] or [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", text[:1500])[:1]]
    author = str(getattr(getattr(paper, "metadata", None), "author", "") or "").split(";")[0].split(",")[0].strip()
    return {"doi": doi, "arxiv": arxiv, "year": years[0] if years else None, "surname": (author.split() or [""])[-1].lower()}


def _content(text):
    return [w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in _STOP and len(w) > 2]


def normalise(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _entries(session):
    paper = getattr(session, "paper", None)
    return [(r.reference_number, normalise(r.raw_text), r.raw_text) for r in getattr(paper, "references", []) or [] if (r.raw_text or "").strip()]


def find_links(views, sessions):
    """{"links": [{citing, cited, reference_number, evidence, method}], "ambiguous": [...], "unmatchable": [titles], "cycles": [[a, b]]} over the analysed papers. `views` have session_id and title."""
    titles = {view["session_id"]: normalise(view["title"]) for view in views}
    usable = {sid: t for sid, t in titles.items() if len(t.split()) >= MIN_TITLE_WORDS and len(t) >= MIN_TITLE_CHARS}
    known = {session.session_id: identifiers(session) for session in sessions}
    unmatchable = [view["title"] for view in views if view["session_id"] not in usable and not (known.get(view["session_id"], {}).get("doi") or known.get(view["session_id"], {}).get("arxiv"))]
    by_id = {view["session_id"]: view for view in views}
    words = {sid: _content(by_id[sid]["title"]) for sid in titles}
    links, ambiguous, seen = [], [], set()

    def by_method(citing, plain, raw):
        """[(method, [paper ids])] in order of trust, each only when it found something."""
        raw_dois, raw_arxiv = _doi(raw), _arxiv(raw)
        steps = [("doi", [sid for sid, k in known.items() if sid != citing and k["doi"] & raw_dois]),
                 ("arxiv_id", [sid for sid, k in known.items() if sid != citing and k["arxiv"] & raw_arxiv]),
                 ("title", [sid for sid, title in usable.items() if sid != citing and f" {title} " in f" {plain} "])]
        tokens = set(plain.split())
        years = {int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", plain)}
        author_year = []
        for sid, k in known.items():
            wanted = set(words[sid])
            if sid == citing or len(wanted) < MIN_CONTENT_WORDS or not k["surname"] or k["year"] is None or k["surname"] not in tokens:
                continue
            if any(abs(y - k["year"]) <= 1 for y in years) and len(wanted & tokens) / len(wanted) >= MIN_TITLE_SHARE:
                author_year.append(sid)
        return [*steps, ("author_year_title", author_year)]

    for session in sessions:
        citing = session.session_id
        for number, plain, raw in _entries(session):
            for method, hits in by_method(citing, plain, raw):
                if not hits:
                    continue
                if len(hits) > 1:
                    ambiguous.append({"citing": citing, "reference_number": number, "papers": hits, "method": method,
                                      "reason": "the entry contains the titles of more than one analysed paper" if method == "title" else f"the entry matches more than one analysed paper by {method.replace('_', ' ')}"})
                elif (citing, hits[0]) not in seen:
                    seen.add((citing, hits[0]))
                    links.append({"citing": citing, "cited": hits[0], "reference_number": number, "evidence": " ".join(raw.split())[:240], "method": method})
                break
    cycles = sorted({tuple(sorted((a["citing"], a["cited"]))) for a in links for b in links if a["citing"] == b["cited"] and a["cited"] == b["citing"]})
    result = {"links": links, "ambiguous": ambiguous, "unmatchable": unmatchable, "cycles": [list(pair) for pair in cycles]}
    for item in result["links"]:
        item["citing_title"], item["cited_title"] = by_id[item["citing"]]["title"], by_id[item["cited"]]["title"]
    return result


def shared_references(sessions, ignore=()):
    """References two or more of the papers have in common (the same normalised text of at least 40 characters), each listed once: [{reference, papers: [session ids]}], and the totals
    {"total": entries across papers, "unique": distinct entries}."""
    seen, total = {}, 0
    for session in sessions:
        for _, plain, raw in _entries(session):
            total += 1
            if len(plain) >= 40:
                seen.setdefault(plain, {"reference": " ".join(raw.split())[:240], "papers": []})
                if session.session_id not in seen[plain]["papers"]:
                    seen[plain]["papers"].append(session.session_id)
    shared = sorted((v for v in seen.values() if len(v["papers"]) > 1), key=lambda v: (-len(v["papers"]), v["reference"]))
    return shared, {"total": total, "unique": len({k for k in seen}) + sum(1 for s in sessions for _, p, _ in _entries(s) if len(p) < 40)}
