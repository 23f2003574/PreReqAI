import hashlib
import re
import unicodedata
from copy import deepcopy
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
    return inner in outer and re.search(rf"\b{re.escape(inner)}\b", outer) is not None  # the plain substring test rejects almost every pair before a regex is built


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


# Shared vocabulary that shows the text is about machine learning; an ambiguous concept's own `context` patterns add to it. It names no
# ambiguous concept (attention, dropout, embedding, overfitting), so two everyday words cannot vouch for each other.
_ML_CONTEXT = (
    r"neural net(?:work)?s?", r"deep learning", r"machine learning", r"transformer (?:model|network|architecture|layer|block|encoder|decoder)s?", r"transformer-based", r"gradient", r"backprop", r"classifiers?",
    r"softmax", r"loss function", r"fine-?tun", r"language models?", r"convolution", r"recurrent", r"stochastic",
)


@lru_cache(maxsize=None)
def _technical_pattern(concept):
    """One compiled alternation of a concept's technical phrases: a mention inside one is technical wherever it occurs."""
    return re.compile(rf"(?<![a-z0-9])(?:{'|'.join(concept.technical) or '(?!)'})(?![a-z0-9])")


@lru_cache(maxsize=None)
def _context_pattern(concept):
    shared = [cue for cue in _ML_CONTEXT if not re.fullmatch(cue, concept.name.lower())]  # a concept's own name never vouches for itself ("transformers?" for Transformer)
    return re.compile(rf"(?<![a-z0-9])(?:{'|'.join((*shared, *concept.context))})")


@lru_cache(maxsize=None)
def _anchor_pattern():
    """Every name and alias of the concepts that are not everyday words, as one pattern: such a term near a bare mention shows the text is technical there."""
    registry = ConceptRegistry().all()
    terms = sorted({term.lower() for c in registry if not c.ambiguous for term in (c.name, *c.aliases) if len(term) > 3}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(term) for term in terms) + r")s?(?![a-z0-9])")


ALIAS_WINDOW = 200  # characters on each side of a guarded alias (Concept.alias_context) that may hold one of its context cues


def alias_context_cue(concept, text, start, end, aliases):
    """The context cue found within ALIAS_WINDOW characters of text[start:end] (the alias itself left out) for one of `aliases` of `concept`, or None when the alias has none."""
    for guarded, cues in concept.alias_context:
        if any(alias.lower() in guarded for alias in aliases):
            window = text[max(0, start - ALIAS_WINDOW):start] + " " + text[end:end + ALIAS_WINDOW]
            found = re.search("|".join(cues), window, re.IGNORECASE)
            if found:
                return found.group()
    return None


def unsupported_alias_mentions(concept, text):
    """How many mentions of the concept's guarded aliases have none of their context cues close by: they are not the concept (a "CNN" column of a results table)."""
    rejected = 0
    for guarded, cues in concept.alias_context:
        for alias in guarded:
            for match in re.finditer(rf"(?<![a-z0-9]){re.escape(alias.lower())}s?(?![a-z0-9])", text):
                if alias_context_cue(concept, text, match.start(), match.end(), (alias,)) is None:
                    rejected += 1
    return rejected


LOCAL_WINDOW = 250  # characters on each side of a bare mention that may hold its technical evidence


def _locally_technical(concept, text, occurrences):
    """`occurrences` reduced to the mentions of an ambiguous concept that are technical where they stand: inside one of its technical phrases, or with technical evidence (the
    concept's own context words or the shared machine-learning vocabulary) within LOCAL_WINDOW characters. Never more than `occurrences`."""
    technical = len(_technical_pattern(concept).findall(text))
    terms = sorted({concept.name.lower(), *(alias.lower() for alias in _aliases(concept))}, key=len, reverse=True)
    needle = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")s?\b")
    cue, bare = _context_pattern(concept), 0
    for match in needle.finditer(text):
        window = text[max(0, match.start() - LOCAL_WINDOW):match.end() + LOCAL_WINDOW]
        if cue.search(window.replace(match.group(), " ")) or _anchor_pattern().search(window):  # technical words, or a concept that is not an everyday word, close by
            bare += 1
    return min(occurrences, max(technical, bare))


# Phrases that belong to machine learning and almost nowhere else. A document with no unambiguous registry concept needs several distinct ones before its everyday-word concepts
# (attention, embedding, fine-tuning...) count at all: otherwise a neuroscience or linguistics paper is reported as a machine-learning paper.
_ML_CUES = re.compile(
    r"\b(?:neural networks?|deep learning|machine learning|gradient descent|backpropagation|back-propagation|training (?:set|data|loss|examples?)|test set|validation set|loss function|cross-entropy|"
    r"hyper-?parameters?|overfitting|pre-?train(?:ed|ing)|mini-?batch|learning rate|stochastic gradient|softmax|word embeddings?|large language models?|"
    r"reinforcement learning|reward model|supervised learning|classifier|transformer (?:model|architecture|layers?)|self-attention|attention (?:mechanism|heads?|layers?))\b")
MIN_ML_CUES = 2
MIN_WORDS_FOR_GATE = 40  # a snippet shorter than this holds too little text to judge the field of


def ml_cues(text):
    """The different machine-learning-only phrases `text` (lower-cased) contains, hyphens read as spaces."""
    return {re.sub(r"s$", "", match.group().replace("-", " ")) for match in _ML_CUES.finditer(text)}


def _corroborated(concept, evidence):
    """Whether `evidence` (lower-cased paper text) is technical enough for a bare mention of an ambiguous concept to count."""
    return _context_pattern(concept).search(evidence) is not None


class RuleBasedConceptDetector:
    """
    Detects known concepts using exact,
    case-insensitive matching against the
    Concept Registry, counting a concept's
    whole-word aliases (GNN, DDPM, MDP...) too.
    """

    def __init__(self):

        self.registry = ConceptRegistry(custom=True)

    def detect(
        self,
        paper: Paper,
        context_text: str = None,
    ) -> Paper:

        paper.concepts.clear()
        paper.unrecognised_terms = []

        self.registry = ConceptRegistry(custom=True)  # rebuilt for every paper: a concept the learner confirmed since the last one counts
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

        # What the surrounding paper says: an ambiguous concept's bare mention counts only when this holds technical evidence for it. A caller
        # that detects part of a paper (one section) passes the whole body as `context_text`, so a section keeps the evidence of its paper.
        evidence = normalise_text(context_text) if context_text is not None else full_text

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

        pending, found = [], []

        for concept in concepts:

            inside_longer = sum(count(term, True) for term in shadowing[concept])

            occurrences = mentions(concept) - inside_longer - sum(len(re.findall(rx, full_text)) for rx in concept.exclude)

            if concept.alias_context and occurrences > 0:
                masked = full_text
                for rx in concept.exclude:  # already subtracted above: not rejected a second time
                    masked = re.sub(rx, lambda found: " " * len(found.group()), masked)
                occurrences -= unsupported_alias_mentions(concept, masked)

            if occurrences > 0 and concept.ambiguous and context_text is None:  # a section judged on its paper's evidence keeps that evidence; only whole-paper detection looks at the surroundings
                # A bare mention of an everyday word counts where its own surroundings are technical (a window of text around it), whatever the rest of the paper is about: a paper on
                # language models still says "lots of attention" in an example prompt.
                occurrences = _locally_technical(concept, full_text, occurrences)

            if occurrences > 0 and concept.ambiguous and not _corroborated(concept, evidence):
                pending.append((concept, occurrences))  # decided below, once the unambiguous concepts are known
                continue

            if occurrences <= 0:
                continue

            found.append((concept, occurrences))

        # An unambiguous concept found in the same text (Self-Attention, Transformer...) is also technical evidence for a bare mention.
        anchored = any(not concept.ambiguous for concept, _ in found)
        paper.domain_abstained = False
        names = {c.name.lower().replace("-", " ") for c, _ in found if not c.ambiguous or c.alias_context}  # an alias-guarded concept (CNN...) is not an everyday word
        cues = ml_cues(full_text)
        if len(full_text.split()) >= MIN_WORDS_FOR_GATE and len(cues) + len(names - cues) < MIN_ML_CUES:
            # document-level gate: too few machine-learning-only phrases or distinct unambiguous concepts, so it is not a machine-learning paper. Only a confirmed custom concept or an
            # unambiguous term the document leans on (three or more mentions) stays; the everyday-word concepts and single stray mentions are abstained from.
            kept = [(c, o) for c, o in found if c.domain == "custom" or (not c.ambiguous and o >= 3)]
            paper.domain_abstained = len(kept) < len(found) + len(pending)
            found, pending = kept, []
        for concept, occurrences in pending:
            if not anchored:
                occurrences = min(occurrences, len(_technical_pattern(concept).findall(full_text)))
            if occurrences > 0:
                found.append((concept, occurrences))

        for concept, occurrences in sorted(found, key=lambda item: concepts.index(item[0])):
            paper.concepts.append(
                DetectedConcept(
                    name=concept.name,
                    domain=concept.domain,
                    occurrences=occurrences,
                )
            )

        paper.concept_coverage = concept_detection_coverage(len(concepts), len(paper.concepts))

        return paper


def section_mentions(paper):
    """{section title: {"concepts": {registry concept: mentions}, "subjects": {prerequisite subject: mentions}}} for the sections that
    mention anything, in the order the sections appear. Bibliography and other back-matter sections are empty, like in detect()."""
    from backend.models import Paper

    fingerprint = hashlib.sha1("\x00".join(f"{p.section_title}\x01{p.content}" for p in getattr(paper, "paragraphs", [])).encode("utf-8", "replace")).hexdigest()
    if fingerprint in _SECTION_CACHE:  # the stages that need it (coverage, report) ask about the same paper: the answer is worked out once
        return deepcopy(_SECTION_CACHE[fingerprint])
    found = _section_mentions(paper)
    _SECTION_CACHE[fingerprint] = deepcopy(found)
    while len(_SECTION_CACHE) > 4:
        _SECTION_CACHE.pop(next(iter(_SECTION_CACHE)))
    return found


_SECTION_CACHE = {}


def _section_mentions(paper):
    from backend.models import Paper

    titles = list(dict.fromkeys(paragraph.section_title or "" for paragraph in getattr(paper, "paragraphs", [])))
    found = {}
    whole = body_text(paper)  # the evidence an ambiguous concept's mentions in a section are judged against
    for title in titles:
        part = Paper(source_path=getattr(paper, "source_path", ""), metadata=None)
        part.paragraphs = [p for p in paper.paragraphs if (p.section_title or "") == title]
        concepts = {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(part, context_text=whole).concepts}
        subjects = {name: count for name, count in subject_mentions(part).items() if count}
        if concepts or subjects:
            found[title] = {"concepts": concepts, "subjects": subjects}
    return found
