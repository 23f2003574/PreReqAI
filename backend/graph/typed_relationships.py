"""Typed concept relationships that a sentence of the paper states, each with its exact quotation.

A relationship is added only when ONE sentence names two detected concepts and a cue phrase stands between them : builds_on ("A builds on / is based on / extends B"),
variant_of ("A is a variant / form / special case / instance of B"), uses ("A uses / employs / relies on / is trained with B") and contrasts_with ("A, unlike / in contrast to / rather than B"). The edge
carries the sentence, its section and page (an exact part of the page text). Concepts that merely appear together stay the weak `co_occurs_with` edge; nothing is inferred from co-occurrence."""
import re

from backend.evidence import _pattern, quotable_sentences

TYPES = {
    "builds_on": re.compile(r"\b(?:builds? (?:up)?on|is built (?:up)?on|(?:is |are )?based on|extends?|an extension of|improves? (?:up)?on)\b", re.IGNORECASE),
    "variant_of": re.compile(r"\b(?:is|are) (?:a |an |the )?(?:\w+ )?(?:variant|variation|version|form|type|kind|case|instance|flavou?r) of\b|\b(?:variants?|versions?|special cases?) of\b", re.IGNORECASE),
    "uses": re.compile(r"\b(?:uses?|using|employs?|relies on|rely on|(?:is|are) trained (?:with|using|by)|applies|apply|optimi[sz]es? (?:with|using)|leverages?)\b", re.IGNORECASE),
    "contrasts_with": re.compile(r"\b(?:unlike|in contrast (?:to|with)|rather than|instead of|as opposed to|compared (?:to|with)|differs? from|versus|vs\.?)\b", re.IGNORECASE),
}
_NEGATION = re.compile(r"\b(?:not|no|never|without|cannot|n't)\b", re.IGNORECASE)


def _mentions(sentence, patterns):
    found = []
    for name, pattern in patterns.items():
        match = pattern.search(sentence)
        if match:
            found.append((match.start(), match.end(), name))
    found.sort()
    kept = []
    for item in found:  # a mention inside a longer concept's mention is not a second concept ("Attention" in "Multi-Head Attention")
        if not any(other[0] <= item[0] and item[1] <= other[1] and other is not item for other in found):
            kept.append(item)
    return kept


def find(paper):
    """[(source concept, target concept, relationship, passage)] for the typed relationships the paper's sentences state; at most one per ordered pair and type."""
    from backend.concepts.concept_registry import ConceptRegistry

    registry = {c.name: c for c in ConceptRegistry(custom=True).all()}
    patterns = {c.name: _pattern(registry[c.name]) for c in getattr(paper, "concepts", []) if c.name in registry}
    pages = {page.page_number: " ".join(page.text.split()) for page in getattr(paper, "pages", []) or []}
    seen, found = set(), []
    for _, _, _, section, sentence, page in quotable_sentences(paper) if getattr(paper, "paragraphs", None) else []:
        flat = " ".join(sentence.split())
        if page in pages and flat not in pages[page]:
            continue
        mentions = _mentions(flat, patterns)
        for (start_a, end_a, a), (start_b, end_b, b) in zip(mentions, mentions[1:]):
            if a == b:
                continue
            between = flat[end_a:start_b]
            for relationship, cue in TYPES.items():
                cued = cue.search(between)
                if not cued or len(between.split()) > 8 or _NEGATION.search(between[:cued.start()][-24:] + between[cued.start():cued.end()]):
                    continue  # no cue between the two concepts, too far apart, or the cue is negated ("does not use")
                pair = (a, b, relationship)
                if pair in seen:
                    continue
                seen.add(pair)
                found.append((*pair, {"sentence": flat, "page_number": page, "section": section, "cue": relationship}))
    return found
