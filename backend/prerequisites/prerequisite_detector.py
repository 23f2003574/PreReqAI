import logging

from backend.concepts.concept_registry import ConceptRegistry
from backend.prerequisites import prerequisite_graph
from backend.models import (
    Paper,
    Prerequisite,
)


logger = logging.getLogger("prereqai.prerequisites")


class PrerequisiteDetector:
    """
    Identifies prerequisite concepts required
    to understand a research paper.

    The initial implementation uses deterministic
    rules derived from the detected concepts.
    """

    PREREQUISITE_RULES = prerequisite_graph.rules()  # versioned data with per-edge provenance: prerequisite_graph.json and the modern ML concepts (see prerequisite_graph.py)

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        from backend import custom_concepts

        rules = {**self.PREREQUISITE_RULES, **custom_concepts.confirmed_rules()}  # plus the prerequisites the learner confirmed for their own concepts (never the unconfirmed proposals)

        paper.prerequisites.clear()

        paper.concepts_without_rules = [
            concept.name for concept in paper.concepts if concept.name not in rules
        ]

        if paper.concepts_without_rules:

            logger.warning(
                "no prerequisite rule for detected concepts (their prerequisites are unknown, not absent): %s",
                ", ".join(paper.concepts_without_rules),
            )

        # A prerequisite needed by several concepts is listed once, and its reason names every concept that
        # needs it (not only the first one found), so the learner sees how much of the paper depends on it.
        needed_by = {}

        for concept in paper.concepts:

            for prerequisite in rules.get(
                concept.name,
                [],
            ):

                needed_by.setdefault(prerequisite, []).append(concept.name)

        # A prerequisite the paper does not discuss may itself need others (a graph attention paper needs Attention,
        # which needs Probability): the learner must study those too, or the plan would send them to a course that
        # assumes knowledge the plan never covers. Only prerequisites not already listed are added this way.
        direct = list(needed_by)
        for prerequisite in direct:
            pending, seen = list(rules.get(prerequisite, [])), {prerequisite}
            while pending:
                deeper = pending.pop(0)
                if deeper in seen:
                    continue
                seen.add(deeper)
                if deeper not in direct:
                    for concept in needed_by[prerequisite]:
                        if concept not in needed_by.setdefault(deeper, []):
                            needed_by[deeper].append(concept)
                pending.extend(rules.get(deeper, []))
        # Importance comes only from dependency evidence, with no tuned weights. `confidence` is the share of the paper's
        # rule-bearing concepts (those with at least one prerequisite) that need the prerequisite, directly or through
        # another prerequisite: a measured fraction, not a certainty. A prerequisite needed by at least half of them
        # (dependents * 2 >= total) is "essential", otherwise "supporting". The mentions of the dependent concepts break
        # ties when ranking (see rank_prerequisites); the list itself keeps the rule order.
        occurrences = {}
        for concept in paper.concepts:  # a missing or non-positive count is "unknown", never an invented zero
            count = getattr(concept, "occurrences", None)
            occurrences[concept.name] = count if isinstance(count, int) and count > 0 else None
        total = sum(1 for concept in paper.concepts if rules.get(concept.name))

        # Where each dependent concept is discussed: its sections, and the instructional ones among them (from the paper's own paragraphs).
        where = {}
        if paper.concepts and getattr(paper, "paragraphs", None):
            from backend.concepts.rule_based_concept_detector import section_mentions
            from backend.prerequisites.missing_prerequisite_analyzer import section_role, section_roles

            roles = section_roles([section.title for section in getattr(paper, "sections", [])])
            for title, found in section_mentions(paper).items():
                for name in found["concepts"]:
                    where.setdefault(name, []).append((title, roles.get(title) or section_role(title)))
        ambiguous = {c.name for c in ConceptRegistry().all() if c.ambiguous}

        for prerequisite, concepts in needed_by.items():

            share = len(concepts) / total if total else 0.0
            essential = bool(total) and len(concepts) * 2 >= total
            mentions = sum(occurrences.get(name) or 0 for name in concepts)
            unknown = [name for name in concepts if occurrences.get(name) is None]
            reasons = []
            evidence = [
                {"concept": name, "relation": "direct" if prerequisite in rules.get(name, ()) else "indirect",
                 "occurrences": occurrences.get(name)}
                for name in concepts
            ]

            graded = []
            for item in evidence:
                places = where.get(item["concept"], [])
                grade, why = grade_concept(item["occurrences"], [t for t, role in places if role == "instructional"], len(places),
                                           item["concept"] in ambiguous, item["relation"] == "indirect")
                graded.append((grade, item["relation"] == "direct"))
                reasons.append(f"{item['concept']}: {why}")
            direct = occurrences[prerequisite] if prerequisite in occurrences else direct_subject_mentions(paper, prerequisite)
            strength, direct_reason = grade_with_direct_mentions(grade_prerequisite(graded), direct, prerequisite)
            reasons.append(direct_reason)

            paper.prerequisites.append(

                Prerequisite(

                    concept=prerequisite,

                    reason=(
                        f"Required to understand "
                        f"{', '.join(concepts)}"
                    ),

                    confidence=round(share, 2),

                    importance="essential" if essential else "supporting",

                    importance_reason=(
                        f"Needed by {len(concepts)} of the paper's {total} concepts that have prerequisites "
                        f"({mentions} mentions{f'; no mention count for {len(unknown)}' if unknown else ''}): "
                        f"{'essential' if essential else 'supporting'}."
                    ),

                    dependent_mentions=mentions,

                    evidence=evidence,

                    evidence_strength=strength,

                    strength_reasons=reasons,

                    evidence_note=(
                        f"This is an association from PreReqAI's built-in prerequisite table, not something the paper states. "
                        f"The paper was only checked for mentions of {', '.join(concepts)}."
                    ),
                )
            )

        from backend.parsing.stated_prerequisites import apply as apply_stated

        return apply_stated(paper)  # what the paper itself says it needs: provenance, one grade up for explicit cues


# The evidence grade of a dependent concept (the concept whose prerequisite table entry produced a recommendation), from what the paper shows:
#   mentions   MIN_REPEATED or more counted mentions are "repeated"; one or two are "isolated"; no usable count is unknown and earns nothing.
#   sections   a mention in an instructional section (Background, Preliminaries, Method...) or mentions in two or more sections show the paper
#              works with the concept, not merely names it. Without section data (no paragraphs) only the mentions are used.
#   strong     repeated and (taught or spread out); moderate: repeated, or taught; weak: anything else.
#   ambiguous  a concept that is also an everyday word (see Concept.ambiguous) is weak unless repeated.
#   indirect   a prerequisite reached only through another prerequisite grades at most moderate.
# A recommendation is strong with a strong direct dependent, or with two dependents graded moderate or better when one of them is direct;
# moderate with any dependent graded moderate or better; otherwise weak. One incidental mention can therefore never make it strong.
MIN_REPEATED = 3
_RANK = {"weak": 0, "moderate": 1, "strong": 2}


def grade_concept(mentions, instructional, sections, ambiguous=False, indirect=False):
    """(grade, reason) for one dependent concept; see the rules above."""
    repeated = isinstance(mentions, int) and mentions >= MIN_REPEATED
    taught = bool(instructional)
    spread = sections >= 2
    if mentions is None:
        grade, why = "weak", "no mention count"
    elif ambiguous and not repeated:
        grade, why = "weak", f"{mentions} mention{'s' if mentions != 1 else ''} of a word that is also everyday language"
    elif repeated and (taught or spread):
        grade, why = "strong", f"{mentions} mentions, " + ("in " + ", ".join(instructional) if taught else f"across {sections} sections")
    elif repeated:
        grade, why = "moderate", f"{mentions} mentions, none in a Background or Method-like section"
    elif taught:
        grade, why = "moderate", f"{mentions} mention{'s' if mentions != 1 else ''}, in {', '.join(instructional)}"
    else:
        grade, why = "weak", f"{mentions} mention{'s' if mentions != 1 else ''}, an incidental mention"
    if indirect and grade == "strong":
        grade, why = "moderate", why + "; needed only through another prerequisite"
    return grade, why


def grade_prerequisite(grades):
    """'strong', 'moderate' or 'weak' from [(grade, direct)] of the dependent concepts."""
    good = [direct for grade, direct in grades if _RANK[grade] >= 1]
    if any(grade == "strong" and direct for grade, direct in grades) or (len(good) >= 2 and any(good)):
        return "strong"
    return "moderate" if good else "weak"


def direct_subject_mentions(paper, subject):
    """How often the paper itself names a prerequisite that is not a registry concept (Linear Algebra, Calculus...); None when it cannot be counted."""
    from backend.concepts.rule_based_concept_detector import subject_mentions

    try:
        return subject_mentions(paper).get(subject, 0)
    except Exception:  # no usable text: an unknown count, never an invented zero
        return None


def grade_with_direct_mentions(grade, direct, name):
    """(grade, reason): the grade from the dependents, adjusted by how often the paper names the prerequisite itself. A dependent's mentions show the
    paper needs the idea; only the paper's own mentions of it show the paper leans on it: a prerequisite the paper never names (or whose count is
    unknown) is at most moderate however many dependents it has, and one it names MIN_REPEATED or more times is lifted one step (weak to moderate,
    moderate to strong). One or two mentions leave the grade as it is."""
    if not isinstance(direct, int) or direct <= 0:
        why = f"{name} itself is never named in the paper" if direct == 0 else f"no count of how often the paper names {name} itself"
        if grade == "strong":
            return "moderate", why + ", so at most moderate"
        return grade, why
    if direct >= MIN_REPEATED:
        lifted = {"weak": "moderate", "moderate": "strong", "strong": "strong"}[grade]
        return lifted, f"{name} itself is named {direct} times in the paper" + ("; one grade up for that" if lifted != grade else "")
    return grade, f"{name} itself is named {direct} time{'s' if direct != 1 else ''} in the paper"


def rank_prerequisites(prerequisites):
    """Prerequisites most-needed first: by the number of dependent concepts (the length of `evidence`, one entry per dependent), then by
    the mentions of those concepts, then by name, so equal evidence always ranks the same way."""
    return sorted(prerequisites, key=lambda p: (-len(p.evidence), -p.dependent_mentions, p.concept))
