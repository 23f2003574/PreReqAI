"""Candidate concepts a paper uses that PreReqAI's registry does not know, for the learner to confirm (never added by themselves).

Two kinds of evidence, in the paper's own words: a DEFINITION (the paper abbreviates a phrase "natural selection (NS)", "we call X", "X is defined as", "so-called X", "also known as X",
"referred to as X") and REPETITION (a two- or three-word phrase that occurs at least MIN_MENTIONS times across at least MIN_PARAGRAPHS paragraphs and does not start or end with a function
word). Each candidate carries the sentence that shows it, its page and section, how often it is mentioned, and why it was proposed; candidates are ranked by definition first, then
spread and frequency, and phrases the registry already knows (by name or alias) are dropped. Nothing here enters the prerequisite graph: a confirmed concept is detected like any other but has no
prerequisite rules, which PreReqAI reports as unsupported rather than as needing nothing."""
import re

MIN_MENTIONS, MIN_PARAGRAPHS, MAX_CANDIDATES = 3, 2, 20
_STOP = frozenset("""a an the of and or in on at to for with by from as is are was were be been being this that these those it its we our us they their there here which who whom whose what when where while
how why not no nor but if then than so such can could may might must shall should will would do does did done have has had having also both each other some any all more most many much one two three first second
new use used using based given let thus hence per via over under between among into within without across about after before during further however therefore moreover although because since only very""".split())
_WORD = r"[A-Za-z][A-Za-z\-]{2,}"
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[“\"])")
_ABBREVIATED = re.compile(rf"\b((?:{_WORD})(?: {_WORD}){{1,3}}) \(([A-Z][A-Za-z]{{1,7}}s?)\)")
_NAMED = re.compile(rf"(?:\bso-called |\balso known as |\bknown as |\breferred to as |\b(?:is|are) called )[\"\u201c]?({_WORD}(?: {_WORD}){{0,2}})", re.IGNORECASE)
_WE_CALL = re.compile(rf"\bwe (?:call|term|define|denote)\b[^.]{{0,25}}?\b(?:as )?(?:the )?[\"\u201c]?({_WORD}(?: {_WORD}){{1,2}})", re.IGNORECASE)  # at least two words: "we call the spread" is not a term
_DEFINED = re.compile(rf"\b({_WORD}(?: {_WORD}){{0,2}}) (?:is|are) defined as\b", re.IGNORECASE)
_BACK = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references|bibliography|acknowledg|appendix)", re.IGNORECASE)


def _usable(term):
    words = term.lower().split()
    return 4 <= len(term) <= 50 and not any(char.isdigit() for char in term) and words[0] not in _STOP and words[-1] not in _STOP and not all(w in _STOP for w in words)


def _known_terms():
    from backend.concepts.concept_registry import ConceptRegistry

    return {term.lower() for concept in ConceptRegistry().all() for term in (concept.name, *concept.aliases)}


def _initials_match(phrase, acronym):
    initials = "".join(word[0] for word in re.split(r"[ -]", phrase.lower()) if word).upper()
    return acronym.rstrip("s").upper() in initials or initials.endswith(acronym.rstrip("s").upper()[-2:])


def find(paper, known=None, limit=MAX_CANDIDATES):
    """[{term, score, reason, mentions, sentence, page_number, section}] ranked best first, at most `limit`. `known`: lower-case terms to leave out (default: the registry)."""
    known = _known_terms() if known is None else known
    paragraphs = [p for p in getattr(paper, "paragraphs", []) if not _BACK.match(p.section_title or "")]
    found = {}

    def add(term, reason, weight, sentence, paragraph, acronym=None):
        term = " ".join(term.split())
        key = term.lower()
        if not _usable(term) or key in known or (acronym and acronym.lower() in known):
            return
        entry = found.setdefault(key, {"term": term, "definition": 0, "reasons": [], "sentence": sentence, "page_number": paragraph.page_number, "section": paragraph.section_title})
        if weight and reason not in entry["reasons"]:
            entry["definition"] += weight
            entry["reasons"].append(reason)
            if weight > 0:
                entry["sentence"], entry["page_number"], entry["section"] = sentence, paragraph.page_number, paragraph.section_title

    for paragraph in paragraphs:
        for sentence in _SENTENCES.split(" ".join((paragraph.content or "").split())):
            for match in _ABBREVIATED.finditer(sentence):
                phrase = " ".join(match.group(1).split())
                words = phrase.split()
                while words and words[0].lower() in _STOP:  # "the natural selection" -> "natural selection"
                    words.pop(0)
                if len(words) >= 2 and _initials_match(" ".join(words), match.group(2)):
                    add(" ".join(words), f"defined with its abbreviation ({match.group(2)})", 3, sentence, paragraph, match.group(2))
            for match in _NAMED.finditer(sentence):
                add(match.group(1), "named by the paper as a term", 2, sentence, paragraph)
            for match in _WE_CALL.finditer(sentence):
                add(match.group(1), "named by the paper as a term", 2, sentence, paragraph)
            for match in _DEFINED.finditer(sentence):
                add(match.group(1), "defined by the paper", 3, sentence, paragraph)
    text = [(p, " ".join((p.content or "").lower().replace("­", "").split())) for p in paragraphs]
    counts, spread = {}, {}
    for position, (paragraph, lowered) in enumerate(text):
        words = re.findall(r"[a-z][a-z\-]{2,}", lowered)
        for size in (2, 3):
            for i in range(len(words) - size + 1):
                gram = words[i:i + size]
                if gram[0] in _STOP or gram[-1] in _STOP or any(w in _STOP for w in gram[1:-1] if size == 3 and w in ("the", "a", "an")):
                    continue
                phrase = " ".join(gram)
                counts[phrase] = counts.get(phrase, 0) + 1
                spread.setdefault(phrase, set()).add(position)
    for phrase, count in counts.items():
        if count >= MIN_MENTIONS and len(spread[phrase]) >= MIN_PARAGRAPHS and phrase not in known and _usable(phrase):
            first = next(p for p, lowered in text if phrase in lowered)
            sentence = next((s for s in _SENTENCES.split(" ".join(first.content.split())) if phrase in s.lower()), "")
            if sentence:
                entry = found.setdefault(phrase, {"term": phrase, "definition": 0, "reasons": [], "sentence": sentence, "page_number": first.page_number, "section": first.section_title})
                entry["reasons"].append(f"repeated: {count} mentions in {len(spread[phrase])} paragraphs")
    ranked = []
    for key, entry in found.items():
        mentions = sum(lowered.count(key) for _, lowered in text)
        inside = sum(1 for other in found if other != key and key in other and found[other]["definition"] >= entry["definition"] and (found[other]["definition"] or counts.get(other, 0) >= MIN_MENTIONS))
        if inside and not entry["definition"]:
            continue  # "natural" "selection" parts of a longer candidate: the longer phrase is the term
        places = len({p.section_title for p, lowered in text if key in lowered})
        ranked.append({"term": entry["term"], "score": round(entry["definition"] * 3 + min(mentions, 10) + places, 2), "reason": "; ".join(entry["reasons"]), "mentions": mentions,
                       "sentence": entry["sentence"], "page_number": entry["page_number"], "section": entry["section"]})
    return sorted(ranked, key=lambda c: (-c["score"], c["term"]))[:limit]
