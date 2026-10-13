import re

from backend.models import (
    Paper,
    DetectedConcept,
)

from .concept_registry import ConceptRegistry


# A bibliography lists titles of other papers ("Graph attention networks", "Policy gradient methods"):
# they say what the paper cites, not what it needs the reader to know, so they are not counted.
_BACK_MATTER = re.compile(r"^[\dIVXLivxl.]*\s*(references|bibliography|works cited|acknowledge?ments?)\b", re.IGNORECASE)


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

        concepts = self.registry.all()

        # PDF text is hard-wrapped: "policy\ngradient" and "multi-\nhead" must still match their concept.
        # A line-end hyphen is a typesetting break ("trans-\nformer" is "transformer") unless the word is
        # a real compound ("self-\nattention"); a joined word that is part of a concept name settles it.
        words = {
            word.rstrip("s")
            for concept in concepts
            for term in (concept.name, *concept.aliases)
            for word in term.lower().split()
        }

        def unwrap(match):
            joined = match.group(1) + match.group(2)
            return joined if joined.rstrip("s") in words else f"{match.group(1)}-{match.group(2)}"

        full_text = re.sub(r"(\w+)-[ \t]*\n\s*(\w+)", unwrap, full_text)
        full_text = re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "-", full_text))

        def mentions(concept):
            return full_text.count(concept.name.lower()) + sum(
                len(re.findall(rf"\b{re.escape(alias.lower())}\b", full_text))
                for alias in concept.aliases
            )

        for concept in concepts:

            name = concept.name.lower()

            # "Self-Attention" and "Multi-Head Attention" contain "attention": mentions of the longer concept
            # (by name or alias) are not also mentions of the shorter one, only a standalone "attention" is.
            inside_longer = sum(
                full_text.count(other.name.lower())
                + sum(
                    len(re.findall(rf"\b{re.escape(alias.lower())}\b", full_text))
                    for alias in other.aliases
                    if name in alias.lower()
                )
                for other in concepts
                if other is not concept and name in other.name.lower()
            )

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
