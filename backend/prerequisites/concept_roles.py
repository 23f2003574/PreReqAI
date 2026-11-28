"""The role each detected concept plays in a paper: what the paper itself contributes, what it builds on, and what it only names in passing.

* contribution: the concept is named in the paper's title, or in a sentence of the front matter, abstract or introduction in which the paper says it proposes, introduces or presents it (`CUE`). Its
  evidence is that exact sentence with its page. A paper's own contribution is not something the reader must know beforehand.
* incidental: in a paper of at least MIN_WORDS words, at most INCIDENTAL_MENTIONS counted mentions, none of them in an instructional (Background, Preliminaries, Method...) section: the paper names it, it does not use it.
* background: every other concept. A background concept the paper uses repeatedly (BACKGROUND_MENTIONS mentions) in at least BACKGROUND_SECTIONS sections, without defining it, is something the reader is
  expected to know already (`background_prerequisites`).
Rule-based and deterministic; the thresholds are reasoned values checked against six real papers whose prerequisite labels are AI-written and PROVISIONAL, not tuned on human ground truth."""
import re

from backend.evidence import _pattern, quotable_sentences

INCIDENTAL_MENTIONS, BACKGROUND_MENTIONS, BACKGROUND_SECTIONS = 2, 6, 3
MIN_WORDS = 2000  # a document shorter than this is a note or an abstract: a concept it names twice is not 'in passing' (there is no body for it to pass through)
CUE = re.compile(r"\b(?:we|this (?:paper|work|study|article)|our (?:work|method|approach|model|models|framework))\s+(?:\w+\s+){0,2}?(?:propose|introduce|present|develop|release|describe|call|study|design)\w*", re.IGNORECASE)
_FRONT = re.compile(r"^(?:front matter|abstract|\d*\.?\s*introduction|summary)\b", re.IGNORECASE)
_DEFINITION = re.compile(r"\b(?:is|are|refers? to|denotes?|is defined as|is called|we define)\b\s+(?:an?|the)\b", re.IGNORECASE)


_PREPOSITION = re.compile(r"\b(?:of|in|for|from|with|over|on|to|by|via|than|against)\b", re.IGNORECASE)


def _is_object_of_cue(sentence, pattern):
    """Whether the concept is what the sentence's 'we propose / introduce / present' is about: it follows the cue within six words with no preposition between (\"we propose Direct Preference Optimization\", not
    \"we introduce a new parameterization of the reward model in RLHF\", which is about a reward model and mentions RLHF as the setting)."""
    for cue in CUE.finditer(sentence):
        match = pattern.search(sentence, cue.end())
        if match:
            between = sentence[cue.end():match.start()]
            if len(between.split()) <= 6 and not _PREPOSITION.search(between):
                return True
    return False


def classify(paper):
    """{concept name: {"role", "mentions", "evidence": [{sentence, page_number, section, why}]}} for the paper's detected concepts."""
    from backend.concepts.concept_registry import ConceptRegistry
    from backend.concepts.rule_based_concept_detector import section_mentions
    from backend.prerequisites.missing_prerequisite_analyzer import section_role, section_roles

    registry = {c.name: c for c in ConceptRegistry(custom=True).all()}
    title = " ".join(str(getattr(getattr(paper, "metadata", None), "title", "") or "").split())
    sentences = [(section, sentence, page) for _, _, _, section, sentence, page in quotable_sentences(paper)] if getattr(paper, "paragraphs", None) else []
    roles = section_roles([s.title for s in getattr(paper, "sections", [])])
    where = {}
    for section, found in (section_mentions(paper) if getattr(paper, "paragraphs", None) else {}).items():
        for name, count in found["concepts"].items():
            where.setdefault(name, []).append((section, roles.get(section) or section_role(section), count))
    long_enough = sum(len((p.content or "").split()) for p in getattr(paper, "paragraphs", []) or []) >= MIN_WORDS
    result = {}
    for concept in getattr(paper, "concepts", []):
        pattern = _pattern(registry[concept.name]) if concept.name in registry else None
        mentions = getattr(concept, "occurrences", None) if isinstance(getattr(concept, "occurrences", None), int) else 0
        places = where.get(concept.name, [])
        evidence, role = [], "background"
        if pattern is not None and title and pattern.search(title):
            evidence.append({"sentence": title, "page_number": 1, "section": "Title", "why": "named in the paper's title"})
        if pattern is not None and mentions >= 3:
            for section, sentence, page in sentences:
                if _FRONT.match(section) and _is_object_of_cue(sentence, pattern):
                    evidence.append({"sentence": sentence, "page_number": page, "section": section, "why": "the paper says it proposes or presents it"})
                    break
        if evidence:
            role = "contribution"
        elif long_enough and mentions <= INCIDENTAL_MENTIONS and not any(kind == "instructional" for _, kind, _ in places):
            role = "incidental"
        result[concept.name] = {"role": role, "mentions": mentions, "sections": len(places), "evidence": evidence}
    return result


def background_prerequisites(paper, roles=None):
    """The names of background concepts the reader is expected to know: used at least BACKGROUND_MENTIONS times across at least BACKGROUND_SECTIONS sections and not defined by the paper (no sentence
    of the form 'X is a ...')."""
    from backend.concepts.concept_registry import ConceptRegistry

    roles = roles if roles is not None else classify(paper)
    registry = {c.name: c for c in ConceptRegistry(custom=True).all()}
    sentences = [sentence for _, _, _, _, sentence, _ in quotable_sentences(paper)] if getattr(paper, "paragraphs", None) else []
    found = []
    for name, info in roles.items():
        if info["role"] != "background" or info["mentions"] < BACKGROUND_MENTIONS or info["sections"] < BACKGROUND_SECTIONS or name not in registry:
            continue
        pattern = _pattern(registry[name])
        defined = any((m := pattern.search(sentence)) and m.start() < 40 and _DEFINITION.match(sentence[m.end():m.end() + 25].lstrip(" ,")) for sentence in sentences)
        if not defined:
            found.append(name)
    return found
