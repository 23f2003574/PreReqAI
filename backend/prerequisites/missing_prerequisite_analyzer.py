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
# Whole words only: "Preference" is not "reference" (a section "Direct Preference Optimization" is the method, not the bibliography). "References" and
# "Bibliography" name the list itself, so they must be (nearly) the whole title; a title merely containing the word "reference" is not one.
_RELATED = re.compile(r"\b(?:related (?:work|research|literature)s?|prior (?:work|art)|previous (?:work|studies)|literature|works cited|acknowledg\w*)\b", re.IGNORECASE)
_BIBLIOGRAPHY = re.compile(r"^(?:references?(?: list)?|bibliography|works cited)$", re.IGNORECASE)
_INSTRUCTIONAL = re.compile(
    r"^(?:background|preliminar(?:y|ies)|notation|problem (?:statement|formulation|setup|setting|definition)|methods?(?:ology)?|approach|"
    r"proposed|models?(?:ing|ling)?|architectur(?:e|es|al)|theory|theoretical|algorithms?|framework|formulation|derivations?)\b",
    re.IGNORECASE,
)
_INTRODUCTION = re.compile(r"^(?:introduction|overview|motivation)\b", re.IGNORECASE)
# Titles that name where results, discussion or extra material go: the method section is over once one of these starts.
_LATER = re.compile(
    r"\b(?:experiment\w*|results?|evaluation|empirical|discussion|conclusions?|limitations?|ablations?|appendix|supplementary|broader impact|ethic\w*|"
    r"dataset|benchmark\w*|analysis|frequently asked|acknowledg\w*|references?|bibliography|author|contributions?)\b",
    re.IGNORECASE,
)


def _title(title):
    return _NUMBER.sub("", (title or "").strip())


def section_role(title):
    """The role a section's title alone gives it (see the policy above); `section_roles` adds the context of the neighbouring sections."""
    title = _title(title)
    if _RELATED.search(title) or _BIBLIOGRAPHY.match(title):
        return "related"
    return "instructional" if _INSTRUCTIONAL.match(title) else "other"


def _top_level(title):
    return bool(re.match(r"^(?:\d+|[IVX]+)\.?\s", (title or "").strip()))


def section_roles(titles):
    """{title: role} for a paper's section titles in reading order. Each title gives its role, and a numbered top-level section whose title
    says nothing (a method named after the paper's own idea: "4 Direct Preference Optimization", "2 Chain-of-Thought Prompting") is instructional
    when it directly follows the Introduction or a Background / Method / Related Work section, and is not one of the results, discussion or
    appendix sections (so "3 Arithmetic Reasoning", which follows the method section, stays "other")."""
    roles, previous = {}, None  # previous: the role-source of the last top-level section: "intro", "title" (recognised by its title), "context" (promoted), None
    for title in titles:
        if title in roles:
            continue
        role, name = section_role(title), _title(title)
        if _INTRODUCTION.match(name):
            previous = "intro"
        elif _top_level(title):
            if role != "other":
                previous = "title"
            elif _LATER.search(name):
                previous = None
            elif previous in ("intro", "title"):
                role, previous = "instructional", "context"
            else:
                previous = None
        roles[title] = role
    return roles


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
            roles = section_roles([section.title for section in getattr(paper, "sections", [])])
            where = [
                {"section": title, "mentions": found[kind][prerequisite.concept], "role": roles.get(title) or section_role(title)}
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
