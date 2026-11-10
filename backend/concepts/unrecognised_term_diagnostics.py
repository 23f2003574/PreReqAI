import re
import unicodedata

# "Graph Isomorphism Network (GIN)": a Title-Case phrase of 2-5 words followed by its parenthesised acronym. Authors define
# technical terms this way, so it is a far less noisy signal than capitalised words (which also open sentences and name people).
_DEFINITION = re.compile(r"\b((?:[A-Z][a-z]+[ -]){1,4}[A-Z][a-z]+)\s*\(([A-Z][A-Za-z]{1,7}s?)\)")


def find_unrecognised_terms(text, registry):
    """Diagnostic only: phrases a paper defines with an acronym ("Phrase Words (ACR)") that the registry does not know,
    neither by phrase nor by acronym. Returns "Phrase Words (ACR)" strings in order of first appearance, without duplicates.
    It never turns a candidate into a detected concept."""
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    known = {
        term.lower()
        for concept in registry.all()
        for term in (concept.name, *concept.aliases)
    }
    found = []
    for match in _DEFINITION.finditer(re.sub(r"\s+", " ", text)):
        phrase, acronym = match.group(1), match.group(2)
        if not re.fullmatch(r"[A-Z]{2,8}s?", acronym):
            continue
        initials = "".join(word[0] for word in re.split(r"[ -]", phrase))
        if not initials.endswith(acronym.rstrip("s")[-2:]) and acronym.rstrip("s") not in initials:
            continue  # the parenthesis does not abbreviate the phrase ("Figure Three (SOTA)")
        if phrase.lower() in known or acronym.lower() in known or acronym.rstrip("s").lower() in known:
            continue
        candidate = f"{phrase} ({acronym})"
        if candidate not in found:
            found.append(candidate)
    return found
