"""Which of the analysed papers cite each other, found conservatively from their reference lists.

A paper A cites an uploaded paper B when one of A's bibliography entries contains B's full title: at least MIN_TITLE_WORDS words and MIN_TITLE_CHARS characters once lower-cased and stripped of punctuation,
so a title like "Attention" can never match. Each link names the reference number and the entry's text. A reference whose text contains the titles of two or more different uploaded papers is
AMBIGUOUS and is listed, not used; a paper whose title is too short to match safely is listed as unmatchable; a paper citing itself is ignored. Links that form a cycle (A cites B and B cites A,
which a revised edition can do) are reported and not used for ordering. Nothing is downloaded or guessed: no match by author, year or similar words."""
import re

MIN_TITLE_WORDS, MIN_TITLE_CHARS = 3, 15


def normalise(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _entries(session):
    paper = getattr(session, "paper", None)
    return [(r.reference_number, normalise(r.raw_text), r.raw_text) for r in getattr(paper, "references", []) or [] if (r.raw_text or "").strip()]


def find_links(views, sessions):
    """{"links": [{citing, cited, reference_number, evidence}], "ambiguous": [...], "unmatchable": [titles], "cycles": [[a, b]]} over the analysed papers. `views` have session_id and title."""
    titles = {view["session_id"]: normalise(view["title"]) for view in views}
    usable = {sid: t for sid, t in titles.items() if len(t.split()) >= MIN_TITLE_WORDS and len(t) >= MIN_TITLE_CHARS}
    unmatchable = [view["title"] for view in views if view["session_id"] not in usable]
    by_id = {view["session_id"]: view for view in views}
    links, ambiguous, seen = [], [], set()
    for session in sessions:
        citing = session.session_id
        for number, plain, raw in _entries(session):
            hits = [sid for sid, title in usable.items() if sid != citing and f" {title} " in f" {plain} "]
            if len(hits) > 1:
                ambiguous.append({"citing": citing, "reference_number": number, "papers": hits, "reason": "the entry contains the titles of more than one analysed paper"})
            elif hits and (citing, hits[0]) not in seen:
                seen.add((citing, hits[0]))
                links.append({"citing": citing, "cited": hits[0], "reference_number": number, "evidence": " ".join(raw.split())[:240]})
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
