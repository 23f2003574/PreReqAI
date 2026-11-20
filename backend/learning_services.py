"""The data the API and the command line both serve for an analysed session: one implementation, so they cannot disagree."""
from backend.evidence import build_evidence
from backend.reading_list import build_reading_list


def reading_list(session, limit=10):
    return build_reading_list(session.paper, limit)


def evidence(session, concept=None):
    """[{concept, occurrences, passages}] for the session's detected concepts, most-mentioned first (the saved report's evidence, recomputed from the paper for an older session that has none);
    only `concept` (any spelling of its name) when given. A concept the paper does not mention gives []."""
    items = list((session.report or {}).get("concept_evidence") or [])
    if not items or not all("passages" in item for item in items):
        found = build_evidence(session.paper)
        items = [{"concept": c.name, "domain": c.domain, "occurrences": c.occurrences, "passages": found.get(c.name, [])}
                 for c in sorted(session.paper.concepts, key=lambda item: -item.occurrences)]
    items = [{"concept": item["concept"], "occurrences": item["occurrences"], "passages": item["passages"]} for item in items]
    if concept:
        wanted = " ".join(str(concept).replace("-", " ").split()).casefold()
        items = [item for item in items if " ".join(item["concept"].replace("-", " ").split()).casefold() == wanted]
    return items
