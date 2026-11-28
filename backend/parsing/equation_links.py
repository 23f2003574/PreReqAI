"""Where the paper itself talks about each equation, and what its symbols mean, with exact quotations.

* references: the sentences that cite the equation by its number ("Eq. 5", "Eqs. (5) and (6)", "equation 7"), found among the paper's quotable sentences, each with its section and page.
* introduction: the sentence that leads into the equation (the last sentence of its section's text before the display), when the equation carries no reference.
* symbols: definitions written as "where X denotes / is / represents ...", "with X the ..." in a sentence near the equation (its own section, the display's page), each a verbatim part of that sentence.
Every sentence is an exact part of the text of the page it cites (a quotation); nothing is paraphrased. Concepts are those the registry finds in the cited sentences."""
import re

from backend.evidence import quotable_sentences

_EQ = re.compile(r"\b(?:eqs?\.?|equations?)\s*\(?\s*(\d{1,3}(?:\.\d+)?)\)?(?:\s*(?:,|and|&|-|–|to)\s*\(?\s*(\d{1,3}(?:\.\d+)?)\)?)*", re.IGNORECASE)
_NUMBERS = re.compile(r"\d{1,3}(?:\.\d+)?")
_SYMBOL = r"(?:[A-Za-zΑ-ω][\w∗′ˆθπ]*(?:\([^()]{0,24}\))?)"
_DEFINES = re.compile(rf"(?:\bwhere\b|\bwith\b|\bhere,?)\s+(?P<first>{_SYMBOL})\s+(?:denotes?|is|are|represents?|stands? for|refers? to|being)\s+(?P<meaning>[^.;]{{3,120}})|(?:,|;|\band\b)\s+(?P<next>{_SYMBOL})\s+(?:denotes?|is|are|represents?|stands? for)\s+(?P<more>[^,.;]{{3,80}})")


def _flat(text):
    return " ".join(str(text).split())


def numbers_cited(sentence):
    """The equation numbers a sentence cites ("Eq. 5 and 6" -> {"5", "6"})."""
    found = set()
    for match in _EQ.finditer(sentence):
        found |= set(_NUMBERS.findall(match.group()))
    return found


def _lead_in(equation, pages, passage):
    """The sentence that leads into the display: the last sentence of the page text before the equation's first piece (within 400 characters), cut only at a sentence end and verbatim from the page."""
    from backend.sentences import split_sentences

    text = pages.get(getattr(equation, "page_number", None))
    anchor = _flat(getattr(equation, "anchor", "") or equation.expression)
    for key in (anchor, anchor[:14]):
        at = text.find(key) if text and key else -1
        if at > 0:
            before = text[max(0, at - 400):at].strip()
            sentences = [s for s in split_sentences(before) if len(s) >= 25]
            if sentences and sentences[-1] in text:
                return passage(equation.section, sentences[-1], equation.page_number)
    return None


def link(paper):
    """{equation_id: {"references": [...], "introduction": {...} or None, "symbols": [...]}} for the paper's equations; every entry is a passage {sentence, page_number, section, concepts}."""
    if not getattr(paper, "equations", None) or not getattr(paper, "paragraphs", None):
        return {}
    from backend.tutor.grounding import named_concepts

    names = [c.name for c in getattr(paper, "concepts", []) or []]
    pages = {page.page_number: _flat(page.text) for page in getattr(paper, "pages", []) or []}
    sentences = [(section, _flat(sentence), page) for _, _, _, section, sentence, page in quotable_sentences(paper)]

    def passage(section, sentence, page, **extra):
        return {"sentence": sentence, "page_number": page, "section": section, "concepts": named_concepts(names, sentence), **extra}

    def exact(sentence, page):
        return page is None or page not in pages or sentence in pages[page]

    cited = {}
    for section, sentence, page in sentences:
        for number in numbers_cited(sentence):
            cited.setdefault(number, []).append((section, sentence, page))
    result = {}
    for equation in paper.equations:
        tag = str(getattr(equation, "tag", "") or "")
        references = [passage(s, t, p) for s, t, p in cited.get(tag, []) if exact(t, p)][:3] if tag else []
        symbols, intro = [], None
        near = [(s, t, p) for s, t, p in sentences if s == equation.section and (p is None or equation.page_number is None or abs(p - equation.page_number) <= 1)]
        for section, sentence, page in near:
            for match in _DEFINES.finditer(sentence):
                first, meaning = (match.group("first"), match.group("meaning")) if match.group("first") else (match.group("next"), match.group("more"))
                if first and first in _flat(equation.expression) and exact(sentence, page) and not any(item["symbol"] == first for item in symbols):
                    symbols.append({"symbol": first, "meaning": _flat(meaning), "sentence": sentence, "page_number": page, "section": section})
        if not references:
            intro = _lead_in(equation, pages, passage)
        result[equation.equation_id] = {"references": references, "introduction": intro, "symbols": symbols[:6]}
    return result


def glossary(links):
    """The paper's symbol glossary: [{symbol, meaning, sentence, page_number, section, equations}] over all equations, one entry per symbol and meaning."""
    seen = {}
    for equation_id, found in sorted(links.items()):
        for item in found["symbols"]:
            key = (item["symbol"], item["meaning"])
            entry = seen.setdefault(key, {**item, "equations": []})
            entry["equations"].append(equation_id)
    return list(seen.values())
