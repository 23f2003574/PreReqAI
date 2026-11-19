"""Deterministic grounding checks for a model-written tutor answer: the answer must cite the evidence passages it was given, every cited passage id
and quotation must match the stored passage exactly, and no number in the answer may come from nowhere. Nothing here calls a model; a citation is
never trusted because the model supplied it."""
import json
import re

from backend.evidence import build_evidence

from .tutor_provider import ProviderError

MAX_EVIDENCE, PER_CONCEPT = 6, 2
MIN_QUOTE_CHARS, MAX_CITATIONS = 12, 6
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
_SPACES = re.compile(r"\s+")


def _norm(text):
    return _SPACES.sub(" ", str(text)).strip()


def select_evidence(paper, concept_names):
    """The evidence passages (see backend.evidence) for the concepts a question names: at most PER_CONCEPT each and MAX_EVIDENCE in all, none repeated."""
    found = build_evidence(paper, limit=PER_CONCEPT)
    chosen, seen = [], set()
    for name in dict.fromkeys(concept_names):
        for passage in found.get(name, []):
            if passage["passage_id"] not in seen and len(chosen) < MAX_EVIDENCE:
                seen.add(passage["passage_id"])
                chosen.append(passage)
    return chosen


def verify(raw, answer, evidence, known_text=""):
    """The verified citations of a model reply, [{passage_id, quote, sentence, page_number, section}] taken from the stored passages, or
    ProviderError("ungrounded", why). Checks, in order: a non-empty citation list; every passage id is one that was supplied; every quotation (at
    least MIN_QUOTE_CHARS characters, whitespace ignored) is a verbatim part of that stored passage; every number of the answer appears in a cited
    passage or in `known_text` (the question and the facts supplied)."""
    try:
        data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))
    except ValueError:
        raise ProviderError("ungrounded", "the reply could not be checked against the paper.") from None
    claimed = data.get("citations") if isinstance(data, dict) else None
    if not isinstance(claimed, list) or not claimed:
        raise ProviderError("ungrounded", "the answer cites no passage of the paper.")
    stored = {passage["passage_id"]: passage for passage in evidence}
    verified, seen = [], set()
    for item in claimed[:MAX_CITATIONS * 2]:
        identifier, quote = (item.get("passage_id"), item.get("quote")) if isinstance(item, dict) else (None, None)
        if not isinstance(identifier, str) or identifier not in stored:
            raise ProviderError("ungrounded", f"the answer cites a passage that was not supplied ({str(identifier)[:30]!r}).")
        if not isinstance(quote, str) or len(_norm(quote)) < MIN_QUOTE_CHARS or _norm(quote) not in _norm(stored[identifier]["sentence"]):
            raise ProviderError("ungrounded", f"a quotation attributed to passage {identifier} is not in that passage.")
        if (identifier, _norm(quote)) not in seen:
            seen.add((identifier, _norm(quote)))
            passage = stored[identifier]
            verified.append({"passage_id": identifier, "quote": _norm(quote), "sentence": passage["sentence"], "page_number": passage["page_number"],
                             "section": passage["section"]})
    support = _norm(" ".join([known_text, *(c["sentence"] for c in verified)]))
    for number in _NUMBER.findall(answer):
        if not re.search(rf"(?<![\w.]){re.escape(number)}(?![\w]|[.,]\d)", support):
            raise ProviderError("ungrounded", f"the answer states {number}, which no cited passage supports.")
    return verified[:MAX_CITATIONS]
