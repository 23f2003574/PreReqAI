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
_CONJUNCTIONS = frozenset("and or but vs versus nor than".split())
# A phrase with a finite verb is a clause fragment ("outperforms llama", "gqa achieves"), never a term; academic filler is no term either ("prior work", "inter alia").
_VERBS = frozenset("""outperforms outperform achieves achieve improves improve shows show shown propose proposes proposed demonstrate demonstrates enables enable uses yields obtains obtain exhibits requires require reduces
reduce provides provide allows allow leads lead makes make gives give consists contains includes matches match beats beat surpasses surpass advise advises rewrite rewrites think thinks outperformed achieved
improved started flipped loaded""".split())
_FILLER = frozenset({"prior work", "related work", "future work", "previous work", "recent work", "inter alia", "et al", "state of the art", "this paper", "these results", "our results", "our method", "our approach", "our model", "united states",
                     "ground truth", "natural language", "existing methods", "superior performance", "higher quality", "faster inference", "less bias", "last layers", "every token", "same expert", "google research", "human study",
                     "multiple choice", "intermediate steps", "final answer", "appendix table", "answer choices"})
_FILLER_WORDS = frozenset("our their this these those such same other previous prior recent superior better worse higher lower best last every less faster slower".split())
_WORD = r"[A-Za-z][A-Za-z\-]{2,}"
from backend.sentences import split_sentences
_ABBREVIATED = re.compile(rf"\b((?:{_WORD})(?: {_WORD}){{1,3}}) \(([A-Z][A-Za-z]{{1,7}}s?)\)")
_NAMED = re.compile(rf"(?:\bso-called |\balso known as |\bknown as |\breferred to as |\b(?:is|are) called )[\"\u201c]?({_WORD}(?: {_WORD}){{0,2}})", re.IGNORECASE)
_WE_CALL = re.compile(rf"\bwe (?:call|term|define|denote)\b[^.]{{0,25}}?\b(?:as )?(?:the )?[\"\u201c]?({_WORD}(?: {_WORD}){{1,2}})", re.IGNORECASE)  # at least two words: "we call the spread" is not a term
_DEFINED = re.compile(rf"\b({_WORD}(?: {_WORD}){{0,2}}) (?:is|are) defined as\b", re.IGNORECASE)
_BACK = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references|bibliography|acknowledg|appendix)", re.IGNORECASE)


def _singular(word):
    return word[:-3] + "y" if word.endswith("ies") and len(word) > 5 else word[:-1] if word.endswith("s") and not word.endswith("ss") and len(word) > 3 else word


def _norm(term):
    """A term with hyphens and case ignored and each word reduced to its singular, so "language models" meets "language model" and "Chain-of-Thought" meets "chain of thought"."""
    return " ".join(_singular(w) for w in re.split(r"[\s\-]+", term.lower()) if w)


def _is_fragment(words, term):
    """Whether a phrase is a clause fragment, a conjunction of two things or academic filler rather than one term."""
    if any(w in _VERBS for w in words) or any(w in _CONJUNCTIONS for w in words) or " ".join(words) in _FILLER:
        return True
    return words[0] in _FILLER_WORDS or any(w.endswith("-") for w in words)  # a word cut at a line end ("atten- tion")


def _usable(term):
    words = term.lower().split()
    if len(words) > 1 and _is_fragment(words, term):
        return False
    return 4 <= len(term) <= 50 and not any(char.isdigit() for char in term) and words[0] not in _STOP and words[-1] not in _STOP and not all(w in _STOP for w in words)


def _known_terms():
    from backend.concepts.concept_registry import ConceptRegistry

    terms = {term.lower() for concept in ConceptRegistry().all() for term in (concept.name, *concept.aliases)}
    return terms | {_norm(term) for term in terms}  # the plural or hyphen-free spelling of a known term is the known term


def _initials_match(phrase, acronym):
    initials = "".join(word[0] for word in re.split(r"[ -]", phrase.lower()) if word).upper()
    return acronym.rstrip("s").upper() in initials or initials.endswith(acronym.rstrip("s").upper()[-2:])


def _part_of_known(phrase, known):
    """Whether `phrase` is a strict word-for-word part of a term the registry already knows (\"large language\" in \"large language model\"): a fragment of a known term, not a new one."""
    padded = f" {_norm(phrase)} "
    return any(padded in f" {term} " and term != _norm(phrase) for term in known if " " in term)


def accepts(term, known=None):
    """Whether `term` would be proposed as a candidate on its wording alone: usable (no clause fragment, conjunction or filler) and not a registry concept in any plural or hyphen spelling."""
    known = _known_terms() if known is None else known
    return _usable(term) and term.lower() not in known and _norm(term) not in known


def find(paper, known=None, limit=MAX_CANDIDATES):
    """[{term, score, reason, mentions, sentence, page_number, section}] ranked best first, at most `limit`. `known`: lower-case terms to leave out (default: the registry)."""
    known = _known_terms() if known is None else known
    paragraphs = [p for p in getattr(paper, "paragraphs", []) if not _BACK.match(p.section_title or "")]
    found = {}

    def add(term, reason, weight, sentence, paragraph, acronym=None):
        term = " ".join(term.split())
        key = term.lower()
        if not _usable(term) or key in known or _norm(term) in known or (acronym and acronym.lower() in known):
            return
        entry = found.setdefault(key, {"term": term, "definition": 0, "reasons": [], "sentence": sentence, "page_number": paragraph.page_number, "section": paragraph.section_title})
        if weight and reason not in entry["reasons"]:
            entry["definition"] += weight
            entry["reasons"].append(reason)
            if weight > 0:
                entry["sentence"], entry["page_number"], entry["section"] = sentence, paragraph.page_number, paragraph.section_title

    for paragraph in paragraphs:
        for sentence in split_sentences(" ".join((paragraph.content or "").split())):
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
        for chunk in re.split(r"[.,;:!?()\[\]\"\u201c\u201d]", lowered):  # a phrase never runs across punctuation, so it is a real substring of the paragraph
            words = chunk.split()
            for size in (2, 3):
                for i in range(len(words) - size + 1):
                    gram = words[i:i + size]
                    if not all(re.fullmatch(r"[a-z][a-z\-]{2,}", w) for w in gram) or gram[0] in _STOP or gram[-1] in _STOP or any(w in ("the", "a", "an") for w in gram[1:-1]):
                        continue
                    phrase = " ".join(gram)
                    counts[phrase] = counts.get(phrase, 0) + 1
                    spread.setdefault(phrase, set()).add(position)
    for phrase, count in counts.items():
        if count >= MIN_MENTIONS and len(spread[phrase]) >= MIN_PARAGRAPHS and phrase not in known and _norm(phrase) not in known and _usable(phrase) and not _part_of_known(phrase, known):
            first = next((p for p, lowered in text if phrase in lowered), None)
            if first is None:
                continue
            sentence = next((s for s in split_sentences(" ".join(first.content.split())) if phrase in s.lower()), "")
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
