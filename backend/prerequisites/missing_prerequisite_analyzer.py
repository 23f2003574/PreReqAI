import re

from backend.concepts.rule_based_concept_detector import section_mentions, subject_mentions
from backend.models import (
    Paper,
    MissingPrerequisite,
)


# A prerequisite counts as covered by the paper only when it is discussed, not merely named: at least this many mentions
# (bibliography excluded, as in concept detection), and at least one of them where a paper teaches what it builds on.
COVERAGE_MIN_MENTIONS = 3

# The section policy. A section's role comes from its title (its number is ignored):
#   instructional - Background, Preliminaries, Notation, Problem setup, Method(s), Approach, Model, Architecture, Theory: where a paper
#                   explains the ideas it uses. A mention here can make a prerequisite "covered".
#   related       - Related Work, prior work, References, acknowledgements: mentions cite other work and are not counted at all.
#   other         - everything else (Abstract, Introduction, Experiments...), an unrecognised title and a missing title: counted, but they cannot
#                   by themselves make a prerequisite "covered", so an unknown label never claims coverage.
# A title that is both ("Background and Related Work") is "related": when in doubt, no coverage is claimed.
_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+")
_RELATED = re.compile(r"related|prior work|previous work|literature|reference|bibliograph|works cited|acknowledg", re.IGNORECASE)
_INSTRUCTIONAL = re.compile(
    r"^(?:background|preliminar|notation|problem (?:statement|formulation|setup|setting|definition)|method|approach|proposed|model|architecture|theory|theoretical)",
    re.IGNORECASE,
)


def section_role(title):
    title = _NUMBER.sub("", (title or "").strip())
    if _RELATED.search(title):
        return "related"
    return "instructional" if _INSTRUCTIONAL.match(title) else "other"


class MissingPrerequisiteAnalyzer:
    """
    Determines whether detected prerequisites
    are already covered within the current paper.

    This serves as the first step toward
    personalized prerequisite analysis.
    """

    def analyze(
        self,
        paper: Paper,
    ) -> Paper:

        paper.missing_prerequisites.clear()

        mentions = {
            concept.name: getattr(concept, "occurrences", None)
            for concept in paper.concepts
        }

        subjects = None  # subject-level mention counts, computed once and only when a prerequisite is not a detected concept
        by_section = None  # mentions per section, computed once

        for prerequisite in paper.prerequisites:

            # Detected but with no usable count is missing evidence, which is not the same as the paper never mentioning it.
            detected = prerequisite.concept in mentions
            count = mentions.get(prerequisite.concept)
            count = count if isinstance(count, int) and count > 0 else (None if detected else 0)

            if not detected:  # most subjects (Linear Algebra, Calculus...) are not registry concepts: count their own terms in the text
                subjects = subject_mentions(paper) if subjects is None else subjects
                count = subjects.get(prerequisite.concept, 0)

            by_section = section_mentions(paper) if by_section is None else by_section
            where = [
                {"section": title, "mentions": found[kind][prerequisite.concept], "role": section_role(title)}
                for title, found in by_section.items()
                for kind in ("concepts" if detected else "subjects",)
                if prerequisite.concept in found[kind]
            ]
            counted = sum(item["mentions"] for item in where if item["role"] != "related")
            teaching = [item for item in where if item["role"] == "instructional"]

            satisfied = bool(count) and counted >= COVERAGE_MIN_MENTIONS and bool(teaching)

            if count is None:
                status = "unknown"
                reason = "No mention count is available for this concept, so coverage cannot be judged; requires external study"
            elif satisfied:
                status = "covered"
            elif count:
                status = "mentioned_only"
            else:
                status = "not_mentioned"

            if count is None:
                pass
            elif satisfied:
                reason = (f"Covered within the paper ({count} mentions, {sum(i['mentions'] for i in teaching)} of them in "
                          f"{', '.join(i['section'] for i in teaching)})")
            elif count and counted >= COVERAGE_MIN_MENTIONS:
                reason = (f"Mentioned {count} times in the paper, but none in a Background, Preliminaries or Method section, so it is not "
                          f"taught there; requires external study")
            elif count and not counted:
                reason = (f"Mentioned {count} time{'s' if count != 1 else ''} in the paper, only where other work is cited, "
                          f"too little to count as covered; requires external study")
            elif count:
                reason = (f"Mentioned {count} time{'s' if count != 1 else ''} in the paper, "
                          f"too little to count as covered; requires external study")
            else:
                reason = "Requires external study"

            paper.missing_prerequisites.append(

                MissingPrerequisite(

                    concept=prerequisite.concept,

                    satisfied=satisfied,

                    reason=reason,

                    status=status,

                    mentions=count,

                    sections=where,
                )
            )

        return paper
