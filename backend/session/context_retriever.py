import math
import re
from dataclasses import dataclass, field

from backend.concepts.rule_based_concept_detector import _BACK_MATTER
from backend.models import (
    Paper,
)


@dataclass
class RetrievedContext:

    concepts: list[str]

    sections: list[str]

    equations: list[str]

    # The paragraphs of the paper that best answer the question, best first: {"section", "paragraph_id", "text", "coverage"}. Empty when no
    # paragraph holds evidence for it. Sessions saved before this field existed read the default.
    passages: list = field(default_factory=list)


# Words that carry no topic: question words, auxiliaries and the generic vocabulary of talking about a paper. A question is matched on its
# remaining content terms, so "How does the paper handle X?" is a question about X, and a passage is never evidence merely for sharing these.
_GENERIC = frozenset("""a an the and or but of to in on at by for with from as is are was were be been being do does did can could should would will may
might must it its this that these those there here what which who whom whose why how when where whether if then than so such also very more most much many
some any each other about into over under between within without not no yes i you we they he she me my our your their us them paper papers
article work works study studies author authors section sections describe describes described explain explains explained tell say says said discuss
discusses discussed mention mentions mentioned handle handles handled deal deals approach approaches method methods use uses used using show shows
shown give gives given mean means meant paragraph paragraphs text information thing things way ways case cases example examples""".split())

MAX_PASSAGES = 3
MAX_PASSAGE_CHARS = 600
MIN_PASSAGE_CHARS = 40
MIN_COVERAGE = 0.5  # the share of the question's weighted content terms a passage must contain to count as evidence


def _stem(word):
    for suffix in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def _terms(text):
    """The content terms of a text, lower-cased and stemmed: its words minus numbers, one-letter words and the generic vocabulary."""
    return [_stem(word) for word in re.findall(r"[a-z][a-z\-]+", text.lower()) if word not in _GENERIC and len(word) > 2]


def _excerpt(text, wanted):
    """The paragraph's own words: all of it when short, else the run of whole sentences around the best-matching one (original wording, no rewriting)."""
    text = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", text)).strip()
    if len(text) <= MAX_PASSAGE_CHARS:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best = max(range(len(sentences)), key=lambda i: (len(wanted & {_stem(w) for w in re.findall(r"[a-z][a-z\-]+", sentences[i].lower())}), -i))
    chosen, size = [best], len(sentences[best])
    for index in (*range(best + 1, len(sentences)), *range(best - 1, -1, -1)):
        if size + len(sentences[index]) + 1 > MAX_PASSAGE_CHARS:
            break
        chosen.append(index)
        size += len(sentences[index]) + 1
    return " ".join(sentences[i] for i in sorted(chosen))[:MAX_PASSAGE_CHARS]


def rank_passages(paper, question):
    """[{section, paragraph_id, text, coverage}] for the paper's paragraphs that contain evidence for the question, best first (at most MAX_PASSAGES).
    A passage is ranked by the inverse-document-frequency-weighted share of the question's content terms it contains, so a rare term such as
    "positional" outweighs a common one, and a term the paper never uses counts against every passage. Only passages containing at least half
    of that weight count, and a passage that matches only terms found in over a third of the paper does not count at all. Paper text is data:
    it is only compared and quoted, never read as an instruction."""
    query = set(_terms(question))
    paragraphs = [p for p in getattr(paper, "paragraphs", []) or []
                  if len((p.content or "").strip()) >= MIN_PASSAGE_CHARS and not _BACK_MATTER.match((p.section_title or "").strip())]
    if not query or not paragraphs:
        return []
    bags = [set(_terms(p.content)) for p in paragraphs]
    total = len(paragraphs)
    frequency = {term: sum(term in bag for bag in bags) for term in query}
    weight = {term: math.log((total + 1) / (frequency[term] + 0.5)) + 1 for term in query}  # a term absent from the paper weighs the most
    whole = sum(weight.values())
    ranked = []
    for index, (paragraph, bag) in enumerate(zip(paragraphs, bags)):
        matched = query & bag
        coverage = sum(weight[term] for term in matched) / whole
        specific = [term for term in matched if frequency[term] <= max(1, total / 3)]
        if coverage >= MIN_COVERAGE and specific:
            ranked.append((-coverage, index, paragraph))
    ranked.sort(key=lambda item: item[:2])
    return [{"section": paragraph.section_title or "", "paragraph_id": paragraph.paragraph_id, "text": _excerpt(paragraph.content, query),
             "page_number": getattr(paragraph, "page_number", None), "coverage": round(-negative, 3)} for negative, _, paragraph in ranked[:MAX_PASSAGES]]


class ContextRetriever:
    """
    Retrieves paper context relevant to a learner's question.
    """

    def retrieve(
        self,
        paper: Paper,
        question: str,
    ) -> RetrievedContext:

        concepts = []
        sections = []
        equations = []

        query = question.lower()

        from backend.tutor.grounding import named_concepts  # by name or any alias: "What is DPO?" names Direct Preference Optimization

        aliased = set(named_concepts([concept.name for concept in paper.concepts], question))

        for concept in paper.concepts:

            if concept.name in aliased:

                concepts.append(
                    concept.name,
                )

        for section in paper.sections:

            # the detector ignores the bibliography and acknowledgements; a cited title is not where the paper covers a concept
            if _BACK_MATTER.match((section.title or "").strip()):
                continue

            if any(
                concept.lower() in section.content.lower()
                for concept in concepts
            ):
                sections.append(
                    section.title,
                )

        for equation in paper.equations:

            if equation.section in sections:

                equations.append(
                    equation.expression,
                )

        return RetrievedContext(
            concepts=concepts,
            sections=sections,
            equations=equations,
            passages=rank_passages(paper, question),
        )
