import re
import unicodedata
from functools import lru_cache

from backend.models import (
    Paper,
    DetectedConcept,
)

from .concept_coverage import concept_detection_coverage
from .concept_registry import ConceptRegistry
from .unrecognised_term_diagnostics import find_unrecognised_terms


# A bibliography lists titles of other papers ("Graph attention networks", "Policy gradient methods"):
# they say what the paper cites, not what it needs the reader to know, so they are not counted.
_BACK_MATTER = re.compile(r"^[\dIVXLivxl.]*\s*(references|bibliography|works cited|acknowledge?ments?)\b", re.IGNORECASE)


def body_text(paper):
    """The paper's paragraphs without back matter (references, acknowledgements): what a paper says, not what it cites."""
    return "\n".join(
        paragraph.content
        for paragraph in getattr(paper, "paragraphs", [])
        if not _BACK_MATTER.match((paragraph.section_title or "").strip())
    )


def normalise_text(text):
    """Lower-case text with ligatures (LaTeX PDFs encode "ff", "fi"... as single characters; NFKC expands them), soft hyphens and the
    en/em dashes and non-breaking hyphens of typeset papers (the registry has a plain hyphen) normalised."""
    text = unicodedata.normalize("NFKC", text.lower()).replace("\u00ad", "")
    return re.sub("[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", text)


# Terms that show a paper mentions each prerequisite subject, independent of the concept registry (most subjects have no entry in it).
# Technical phrases only: a bare "graph" (a plot), "probability" (likelihood in everyday speech) or "gradient" is ordinary language, so
# it is not counted ("scaled dot-product attention" is an attention term, so "dot product" is not Linear Algebra). Each pattern is one alternation, so overlapping terms ("multi-head attention mechanism") count once.
_SUBJECT_TERMS = {
    "Linear Algebra": r"linear algebra|matri(?:x|ces) (?:multiplication|product|factori[sz]ation|decomposition|inverse)|eigen(?:value|vector|decomposition)s?"
                      r"|singular value decomposition|svd|vector spaces?|linear (?:transformation|map)s?",
    "Probability": r"probability (?:theory|distributions?|densit(?:y|ies)|mass(?: functions?)?)|(?:conditional|joint|marginal|prior|posterior) (?:probabilit(?:y|ies)|distributions?)"
                   r"|random variables?|bayes['\u2019]? (?:rule|theorem)|bayesian inference|law of total probability",
    "Calculus": r"calculus|partial derivatives?|chain rule|jacobians?|hessians?|taylor (?:expansion|series)|definite integrals?|integration by parts",
    "Information Theory": r"information theory|(?<!cross-)(?<!cross )entropy|kl[ -]divergence|kullback[ -]leibler|mutual information|shannon",
    "Optimization": r"optimi[sz]ation (?:problems?|algorithms?|methods?|landscapes?)|convex (?:optimi[sz]ation|functions?)|learning rate schedules?|local minim(?:a|um)|saddle points?|stochastic optimi[sz]ation",
    "Statistics": r"statistical (?:learning|inference|estimation|models?)|hypothesis tests?|confidence intervals?|bias-variance|sample (?:mean|variance)|maximum a posteriori",
    "Stochastic Processes": r"stochastic (?:processes|process|differential equations?)|markov chains?|brownian motion|wiener process|random walks?|langevin dynamics",
    "Neural Networks": r"neural net(?:work)?s?|multi-?layer perceptrons?|mlps?|feed-?forward (?:neural )?networks?|deep learning",
    "Graphs": r"graph theory|adjacency (?:matri(?:x|ces)|lists?)|(?:directed|undirected|bipartite|weighted|acyclic|connected) graphs?|dags?|graph laplacians?"
              r"|nodes and edges|vertices and edges|knowledge graphs?|spanning trees?|shortest paths?",
    "Attention": r"attention (?:mechanisms?|layers?|heads?|weights?|scores?|maps?)|(?:self|cross|multi[ -]?head|scaled dot-product)[ -]attention|attention is all you need",
    "Transformer": r"transformers?",
    "Markov Decision Process": r"partially observable markov decision process(?:es)?|markov decision process(?:es)?|pomdps?|mdps?",
}

_SUBJECT_PATTERNS = {
    subject: re.compile(rf"(?<![a-z0-9])(?:{terms})(?![a-z0-9])") for subject, terms in _SUBJECT_TERMS.items()
}


def subject_mentions(paper):
    """{prerequisite subject: number of mentions in the paper's body text (back matter excluded)} for every subject, 0 when absent."""
    text = normalise_text(body_text(paper))
    text = re.sub(r"\s+", " ", re.sub(r"-[ \t]*\n\s*", "-", text))  # hard-wrapped lines: "multi-\nhead attention"
    return {subject: len(pattern.findall(text)) for subject, pattern in _SUBJECT_PATTERNS.items()}


@lru_cache(maxsize=None)
def _word_in(inner, outer):
    """Whether `inner` occurs in `outer` as whole words. Registry terms never change, and detect() asks this for every pair of
    terms (concepts x concepts x aliases), which dominated an analysis of any paper; the answer is cached per pair."""
    return re.search(rf"\b{re.escape(inner)}\b", outer) is not None


@lru_cache(maxsize=None)
def _aliases(concept):
    # Aliases match a plural too, so "RNNs" next to "RNN" in the registry would be counted twice: keep the singular only.
    lowered = {alias.lower() for alias in concept.aliases}
    return tuple(alias for alias in concept.aliases if not (alias.lower().endswith("s") and alias.lower()[:-1] in lowered))


@lru_cache(maxsize=None)
def _shadowing_terms(concepts):
    """For each concept, the terms of other concepts whose mentions must not also count for it (with multiplicity). This
    depends only on the registry, not on the paper, so it is computed once instead of for every analysed paper.

    "Self-Attention" and "Multi-Head Attention" contain "attention": mentions of the longer concept (by name or alias) are
    not also mentions of the shorter one, only a standalone "attention" is. The same holds for an alias: "convolutional
    network" inside "graph convolutional network" belongs to the graph concept. Whole words only ("gat" is not in "gated")."""
    shadowing = {}
    for concept in concepts:
        name = concept.name.lower()
        terms = []
        for other in concepts:
            if other is not concept and name in other.name.lower():
                terms.append(other.name)
                terms.extend(alias for alias in _aliases(other) if name in alias.lower())
        own = [alias.lower() for alias in _aliases(concept)]
        counted = {other_term.lower() for other in concepts if other is not concept and name in other.name.lower()
                   for other_term in (other.name, *_aliases(other))}
        for other in concepts:
            if other is concept:
                continue
            for term in (other.name, *_aliases(other)):
                if term.lower() not in counted and any(_word_in(a, term.lower()) and a != term.lower() for a in own):
                    terms.append(term)
        shadowing[concept] = tuple(terms)
    return shadowing


class RuleBasedConceptDetector:
    """
    Detects known concepts using exact,
    case-insensitive matching against the
    Concept Registry, counting a concept's
    whole-word aliases (GNN, DDPM, MDP...) too.
    """

    def __init__(self):

        self.registry = ConceptRegistry()

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        paper.concepts.clear()
        paper.unrecognised_terms = []

        original_text = body_text(paper)
        paper.unrecognised_terms = find_unrecognised_terms(original_text, self.registry)
        full_text = normalise_text(original_text)

        concepts = self.registry.all()

        # PDF text is hard-wrapped: "policy\ngradient" and "multi-\nhead" must still match their concept.
        # A line-end hyphen is a typesetting break ("trans-\nformer" is "transformer") unless the word is
        # a real compound ("self-\nattention"); a joined word that is part of a concept name settles it.
        words = {
            word.rstrip("s")
            for concept in concepts
            for term in (concept.name, *_aliases(concept))
            for word in term.lower().split()
        }

        def unwrap(match):
            joined = match.group(1) + match.group(2)
            return joined if joined.rstrip("s") in words else f"{match.group(1)}-{match.group(2)}"

        full_text = re.sub(r"(\w+)-[ \t]*\n\s*(\w+)", unwrap, full_text)
        full_text = re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "-", full_text))

        # A compound modifier hyphenates a spaced term ("gradient-descent methods" mentions Gradient Descent), unless
        # the registry already lists the hyphenated spelling as a term of its own.
        terms = {term.lower() for concept in concepts for term in (concept.name, *_aliases(concept))}
        for term in terms:
            hyphenated = term.replace(" ", "-")
            if " " in term and hyphenated not in terms and hyphenated in full_text:
                full_text = re.sub(rf"\b{re.escape(hyphenated)}\b", term, full_text)

        counts = {}

        def count(term, plural):
            # Whole-word match: "attention" is not "inattention", nor "softmax" "softmaxed"; names and aliases also match a plural ("GRUs", "ELBOs").
            key = (term, plural)
            if key not in counts:
                needle = term.lower()
                # Most registry terms are absent from a given paper, and a plain substring search rejects them far
                # faster than a regex scan of the whole text; a term that is not a substring cannot match the pattern.
                counts[key] = len(re.findall(rf"\b{re.escape(needle)}{('(?:es)?' if needle.endswith('ss') else 's?') if plural else ''}\b", full_text)) if needle in full_text else 0
            return counts[key]

        def mentions(concept):
            total = count(concept.name, True) + sum(count(alias, True) for alias in _aliases(concept))
            # Two of a concept's own terms (its name or an alias) can overlap ("graph convolutional" inside "graph
            # convolutional network", "monte carlo" inside "Monte Carlo Method"): one mention is counted once, as the longer term.
            terms = [concept.name.lower(), *(alias.lower() for alias in _aliases(concept))]
            for short in terms:
                for longer in terms:
                    if short != longer and _word_in(short, longer):
                        total -= count(longer, True)
            return total

        shadowing = _shadowing_terms(tuple(concepts))

        for concept in concepts:

            inside_longer = sum(count(term, True) for term in shadowing[concept])

            occurrences = mentions(concept) - inside_longer

            if occurrences <= 0:
                continue

            paper.concepts.append(
                DetectedConcept(
                    name=concept.name,
                    domain=concept.domain,
                    occurrences=occurrences,
                )
            )

        paper.concept_coverage = concept_detection_coverage(len(concepts), len(paper.concepts))

        return paper
