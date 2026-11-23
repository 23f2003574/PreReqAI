"""Prerequisites the paper itself states for a concept the learner confirmed, proposed with the sentence that says so.

A sentence proposes "custom concept X needs Y" when a cue stands between the two names: "X builds on Y", "X is built on Y", "X extends Y", "X is based on Y", "X relies on Y", "X requires Y",
"X is defined in terms of Y", "X is a variant / generalisation / special case of Y". X must be a confirmed custom concept and Y a registry concept or subject the planner has study hours for; X is the
nearest mention before the cue and Y the nearest after it, each within MAX_GAP characters, so a sentence naming several concepts is not guessed at (the cue must be directly between them).
Every proposal carries the complete sentence, its page and section. Nothing is stored or planned from a proposal: the learner confirms it (custom_concepts.add_prerequisite)."""
import re

MAX_GAP = 40
CUES = ("builds? (?:up)?on", "(?:is|are) built (?:up)?on", "extends?", "(?:is|are) based on", "relies? on", "requires?", "(?:is|are) defined in terms of", "(?:is|are) an? (?:variant|generali[sz]ation|special case|extension) of",
        "(?:is|are) derived from")
_CUE = re.compile(r"\b(?:" + "|".join(CUES) + r")\b", re.IGNORECASE)
from backend.sentences import split_sentences
_BACK = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references|bibliography|acknowledg|appendix)", re.IGNORECASE)


def _mentions(sentence, terms):
    """[(start, end, canonical)] of every whole-word mention of the terms ({term: canonical}), longest terms first so a longer name is not read as a shorter one inside it."""
    found, taken = [], []
    for term in sorted(terms, key=len, reverse=True):
        for match in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(term) + r"s?(?![A-Za-z0-9])", sentence, re.IGNORECASE):
            if not any(match.start() < end and start < match.end() for start, end in taken):
                taken.append((match.start(), match.end()))
                found.append((match.start(), match.end(), terms[term]))
    return sorted(found)


def propose(paper, custom=None, targets=None, confirmed=None):
    """[{concept, prerequisite, cue, sentence, page_number, section, confirmed: False}] for the paper. `custom`: [{name, aliases}] (default: the confirmed store), `targets`: {lower-case term:
    canonical prerequisite} (default: registry names and aliases, and the subjects, that have study hours), `confirmed`: {concept: [prerequisite names]} already stored (left out)."""
    from backend import custom_concepts

    custom = custom_concepts.load()[0] if custom is None else custom
    if not custom:
        return []
    confirmed = custom_concepts.confirmed_rules() if confirmed is None else confirmed
    if targets is None:
        from backend.concepts.concept_registry import ConceptRegistry
        from backend.prerequisites.prerequisite_graph import BASE_SUBJECTS

        targets = {}
        for concept in ConceptRegistry().all():
            canonical, problem = custom_concepts._target(concept.name)
            if not problem:
                targets.update({term.lower(): canonical for term in (concept.name, *concept.aliases)})
        targets.update({subject.lower(): subject for subject in BASE_SUBJECTS if not custom_concepts._target(subject)[1]})
    own = {term.lower(): item["name"] for item in custom for term in (item["name"], *item["aliases"])}
    found, seen = [], set()
    for paragraph in getattr(paper, "paragraphs", []):
        if _BACK.match(paragraph.section_title or ""):
            continue
        for sentence in split_sentences(" ".join((paragraph.content or "").split())):
            for cue in _CUE.finditer(sentence):
                before = [m for m in _mentions(sentence[:cue.start()], own) if cue.start() - m[1] <= MAX_GAP]
                after = [m for m in _mentions(sentence[cue.end():], targets) if m[0] <= MAX_GAP]
                if not before or not after:
                    continue
                concept, need = before[-1][2], after[0][2]
                if concept == need or need in confirmed.get(concept, []) or (concept, need) in seen:
                    continue
                seen.add((concept, need))
                found.append({"concept": concept, "prerequisite": need, "cue": cue.group(0).lower(), "sentence": sentence, "page_number": paragraph.page_number, "section": paragraph.section_title,
                              "confirmed": False})
    return found
