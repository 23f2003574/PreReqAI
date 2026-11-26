"""Sentence splitting for quoted evidence that does not cut a sentence at an abbreviation.

The paper's own sentences are quoted verbatim (backend/evidence.py), so a sentence cut after "et al." or "Eq." gives a truncated quotation. A boundary is a full stop, question mark
or exclamation mark followed by white space and a capital letter, a digit, a Greek letter, an opening bracket or a quotation mark; it is not a boundary when the text before it ends with a known abbreviation
(et al., Eq., Fig., e.g., i.e., vs., cf., Sec., ...) or a single capital initial ("J. Smith"). "etc." is deliberately not listed: it often ends a sentence."""
import re

_GREEK = "\u0370-\u03ff\u1f00-\u1fff"
_MATH = "$|∇∑∏√∂∫∞‖⟨"  # a sentence may open with a formula: "$x$ is", "|S| is", "∇L is", "∑_i w_i is"
_VARIABLE = r"[a-z](?=\s+(?:is|are|was|were|denotes?|represents?|stands|equals|has|have|gives|controls|determines|being)\b)"  # a lower-case variable as the subject: "k is the number of heads"
_BOUNDARY = re.compile(rf"(?<=[.!?])\s+(?=[A-Z(\[“\"‘]|'\w|\d|[{_GREEK}]|[{re.escape(_MATH)}]|{_VARIABLE})")
# The starts a capital letter does not cover: a digit ("3 layers are used"), a Greek letter ("α controls the rate") and an opening single quotation mark ("'Hello,' she said").
_NON_CAPITAL_START = re.compile(rf"(?:['‘]\w|\d|[{_GREEK}]|[{re.escape(_MATH)}]|{_VARIABLE})")
_LIST_LABEL = re.compile(r"\(?(?:\d{1,3}|[A-Za-z])[.)]+")  # "1." or "(a)." alone is a list label, so the "2" of "1. 2 apples" does not start a sentence
_ABBREVIATIONS = frozenset("""al eq eqs fig figs sec secs sect tab tbl ref refs vs cf eg ie viz approx ca resp no nos vol pp ch thm lem prop cor def alg algs dr prof mr mrs ms st inc ltd""".split())
_LAST_WORD = re.compile(r"(?<![A-Za-z])((?:[A-Za-z]\.)*[A-Za-z]+)\.$")


def _ends_with_abbreviation(piece):
    found = _LAST_WORD.search(piece.rstrip())
    if not found:
        return False
    word = found.group(1)
    if len(word) == 1 and word.isupper():  # an initial: "J. Smith"
        return True
    if "." in word:  # a dotted abbreviation of several letters ("w.r.t.", "U.S.", "Ph.D.", "a.k.a."): "relative to w.r.t. Gaussian noise" and "the U.S. Army" are not sentence ends
        return True
    return word.replace(".", "").lower() in _ABBREVIATIONS


def split_sentences(text):
    """The sentences of `text` as exact, contiguous parts of it (separating white space removed), never ending at an abbreviation."""
    pieces, start, sentences = list(_BOUNDARY.finditer(text)), 0, []
    for match in pieces:
        candidate = text[start:match.start()]
        if _ends_with_abbreviation(candidate):
            continue
        if _NON_CAPITAL_START.match(text, match.end()) and _LIST_LABEL.fullmatch(candidate.strip()):
            continue
        sentences.append(candidate)
        start = match.end()
    sentences.append(text[start:])
    return sentences


_CONTINUATION_OK = ("where ",)  # a lower-case "where ..." after a displayed equation is how mathematical text continues its sentence and reads as one


def is_continuation_fragment(sentence):
    """Whether `sentence` starts in the middle of a sentence or even of a word ("ing instability during fine-tuning,", "et al., 2022); GQA removes..."): its first letter is lower case (text before it, on the
    previous page, column or line of a block the layout split, is missing). Such a fragment is not a complete sentence and is not quoted as one; "where ..." after an equation is the one common
    lower-case opening that is a sentence of its own."""
    text = sentence.lstrip("\"'“‘([{ ")
    if re.match(_VARIABLE, text):  # "k is the number of heads." is a whole sentence about a variable, not the tail of a cut one
        return False
    first = next((c for c in text if c.isalpha()), "")
    return bool(first) and first.islower() and text[:1].isalpha() and not text.lower().startswith(_CONTINUATION_OK)
