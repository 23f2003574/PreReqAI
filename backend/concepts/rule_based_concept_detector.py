import re
import unicodedata

from backend.models import (
    Paper,
    DetectedConcept,
)

from .concept_registry import ConceptRegistry


# A bibliography lists titles of other papers ("Graph attention networks", "Policy gradient methods"):
# they say what the paper cites, not what it needs the reader to know, so they are not counted.
_BACK_MATTER = re.compile(r"^[\dIVXLivxl.]*\s*(references|bibliography|works cited|acknowledge?ments?)\b", re.IGNORECASE)


def _aliases(concept):
    # Aliases match a plural too, so "RNNs" next to "RNN" in the registry would be counted twice: keep the singular only.
    lowered = {alias.lower() for alias in concept.aliases}
    return tuple(alias for alias in concept.aliases if not (alias.lower().endswith("s") and alias.lower()[:-1] in lowered))


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

        full_text = "\n".join(
            paragraph.content
            for paragraph in paper.paragraphs
            if not _BACK_MATTER.match((paragraph.section_title or "").strip())
        ).lower()

        # LaTeX PDFs encode "ff", "fi", "fl"... as ligature characters ("Di\ufb00usion") and may hold soft hyphens;
        # NFKC turns the ligatures (and full-width letters) into plain text.
        full_text = unicodedata.normalize("NFKC", full_text).replace("\u00ad", "")

        # Typeset papers use en/em dashes and non-breaking hyphens where the registry has a plain hyphen.
        full_text = re.sub("[\u2010\u2011\u2012\u2013\u2014]", "-", full_text)

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
            # Two of a concept's own terms can overlap ("graph convolutional" inside "graph convolutional network"):
            # one mention is counted once, as the longer term.
            terms = [alias.lower() for alias in _aliases(concept)]
            for short in terms:
                for longer in terms:
                    if short != longer and re.search(rf"\b{re.escape(short)}\b", longer):
                        total -= count(longer, True)
            return total

        for concept in concepts:

            name = concept.name.lower()

            # "Self-Attention" and "Multi-Head Attention" contain "attention": mentions of the longer concept
            # (by name or alias) are not also mentions of the shorter one, only a standalone "attention" is.
            inside_longer = sum(
                count(other.name, True)
                + sum(count(alias, True) for alias in _aliases(other) if name in alias.lower())
                for other in concepts
                if other is not concept and name in other.name.lower()
            )

            # The same holds for an alias: "convolutional network" inside "graph convolutional network" belongs to
            # the graph concept, not to Convolutional Neural Network. Whole words only ("gat" is not in "gated").
            own = [alias.lower() for alias in _aliases(concept)]
            counted = {other_term.lower() for other in concepts if other is not concept and name in other.name.lower()
                       for other_term in (other.name, *_aliases(other))}
            for other in concepts:
                if other is concept:
                    continue
                for term in (other.name, *_aliases(other)):
                    if term.lower() not in counted and any(re.search(rf"\b{re.escape(a)}\b", term.lower()) and a != term.lower() for a in own):
                        inside_longer += count(term, True)

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

        return paper
