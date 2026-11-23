"""Sentence splitting for quoted evidence that does not cut a sentence at an abbreviation.

The paper's own sentences are quoted verbatim (backend/evidence.py), so a sentence cut after "et al." or "Eq." gives a truncated quotation. A boundary is a full stop, question mark
or exclamation mark followed by white space and a capital letter, an opening bracket or a quotation mark; it is not a boundary when the text before it ends with a known abbreviation
(et al., Eq., Fig., e.g., i.e., vs., cf., Sec., ...) or a single capital initial ("J. Smith"). "etc." is deliberately not listed: it often ends a sentence."""
import re

_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[“\"])")
_ABBREVIATIONS = frozenset("""al eq eqs fig figs sec secs sect tab tbl ref refs vs cf eg ie viz approx ca resp no nos vol pp ch thm lem prop cor def alg algs dr prof mr mrs ms st inc ltd""".split())
_LAST_WORD = re.compile(r"(?<![A-Za-z])((?:[A-Za-z]\.)*[A-Za-z]+)\.$")


def _ends_with_abbreviation(piece):
    found = _LAST_WORD.search(piece.rstrip())
    if not found:
        return False
    word = found.group(1)
    if len(word) == 1 and word.isupper():  # an initial: "J. Smith"
        return True
    return word.replace(".", "").lower() in _ABBREVIATIONS


def split_sentences(text):
    """The sentences of `text` as exact, contiguous parts of it (separating white space removed), never ending at an abbreviation."""
    pieces, start, sentences = list(_BOUNDARY.finditer(text)), 0, []
    for match in pieces:
        candidate = text[start:match.start()]
        if _ends_with_abbreviation(candidate):
            continue
        sentences.append(candidate)
        start = match.end()
    sentences.append(text[start:])
    return sentences
