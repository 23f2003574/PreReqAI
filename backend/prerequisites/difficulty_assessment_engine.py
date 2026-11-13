from backend.models import (
    Paper,
    PaperDifficulty,
)
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner


# Upper bound of missing prerequisite subjects for each level. The rule table has only 9 distinct prerequisite subjects (Transformer joined the 8 base ones as a prerequisite of Vision Transformer), so 9 is the
# most a paper can miss; the bands 0-2, 3-4, 5-6 and 7-9 make every level reachable (the old 6-8 / "more than 8" split never produced Expert).
LEVEL_BANDS = (("Beginner", 2), ("Intermediate", 4), ("Advanced", 6))


def difficulty_level(missing: int) -> str:
    for level, upper in LEVEL_BANDS:
        if missing <= upper:
            return level
    return "Expert"


# The bands above count subjects; the effort a learner faces is hours. Each count band is converted at the mean curated study time per subject
# (the planner's STUDY_TIME table, the only source of hours), so a paper missing an average subject keeps its level, while two missing
# subjects of 27 hours and of 16 hours no longer rate alike. Levels are monotonic in hours by construction.
HOURS_PER_SUBJECT = sum(PrerequisiteLearningPlanner.STUDY_TIME.values()) / len(PrerequisiteLearningPlanner.STUDY_TIME)
HOUR_BANDS = tuple((level, upper * HOURS_PER_SUBJECT) for level, upper in LEVEL_BANDS)


def level_for_hours(hours: float) -> str:
    for level, upper in HOUR_BANDS:
        if hours <= upper:
            return level
    return "Expert"


def prerequisite_effort(paper) -> list:
    """The prerequisites the learner still has to study, one entry per concept: (concept, hours, importance, curated). Hours come from
    the planner's table; a concept without a valid curated estimate counts at the planner's fallback (curated is False), never as 0.
    Largest contributors first: essential before supporting, then more hours, then name."""
    importance = {p.concept: p.importance for p in getattr(paper, "prerequisites", [])}
    todo = {}
    for item in paper.missing_prerequisites:
        if not item.satisfied:
            hours = PrerequisiteLearningPlanner.STUDY_TIME.get(item.concept)
            curated = isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours > 0
            todo.setdefault(item.concept, (item.concept, PrerequisiteLearningPlanner._hours(item.concept), importance.get(item.concept, ""), curated))
    return sorted(todo.values(), key=lambda entry: (entry[2] != "essential", -entry[1], entry[0]))


def describe_contributors(effort: list, limit: int = 3) -> str:
    """"Neural Networks (15h, essential), Linear Algebra (12h)": the biggest contributors, with an uncurated estimate marked."""
    parts = [f"{name} ({hours:g}h{', ' + label if label else ''}{'' if curated else ', estimated'})" for name, hours, label, curated in effort[:limit]]
    return ", ".join(parts) + (f" and {len(effort) - limit} more" if len(effort) > limit else "")


UNKNOWN_LEVEL = "Unknown"  # no concept was detected: the paper's difficulty cannot be judged, which is not the same as easy


class DifficultyAssessmentEngine:
    """
    Estimates the overall difficulty of a
    research paper using prerequisite analysis.
    """

    def assess(
        self,
        paper: Paper,
    ) -> Paper:

        if not paper.concepts and not paper.missing_prerequisites:  # nothing was detected, so "0 missing prerequisites" says nothing about the paper

            paper.difficulty = PaperDifficulty(
                level=UNKNOWN_LEVEL,
                score=0.0,
                explanation=(
                    "Not enough evidence to rate the difficulty: no known concepts were detected in this paper "
                    "(it may be outside the supported topics, or its text could not be read)."
                ),
            )

            return paper

        effort = prerequisite_effort(paper)
        missing = len(effort)
        hours = sum(entry[1] for entry in effort)

        paper.difficulty = PaperDifficulty(

            level=level_for_hours(hours),

            score=round(min(5.0, 1.0 + 0.4 * hours / HOURS_PER_SUBJECT), 1),

            explanation=(
                f"{missing} prerequisite concepts require additional study"
                + (f", about {hours:g} hours; the biggest contributors are {describe_contributors(effort)}." if effort else ".")
            ),
        )

        return paper
