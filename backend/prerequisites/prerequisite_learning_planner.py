import logging
import math

from backend.models import (
    Paper,
    LearningStep,
)


logger = logging.getLogger("prereqai.planner")


class PrerequisiteLearningPlanner:
    """
    Generates a deterministic learning plan
    from the detected missing prerequisites.
    """

    STUDY_ORDER = {

        "Linear Algebra": 1,
        "Probability": 2,
        "Information Theory": 2.5,
        "Calculus": 3,
        "Graphs": 4,
        "Neural Networks": 5,
        "Attention": 7,
        "Self-Attention": 8,
        "Multi-Head Attention": 9,
        "Transformer": 10,
        "Markov Decision Process": 11,
    }

    STUDY_TIME = {

        "Linear Algebra": 12,
        "Probability": 10,
        "Information Theory": 8,
        "Calculus": 10,
        "Graphs": 8,
        "Neural Networks": 15,
        "Attention": 8,
        "Self-Attention": 6,
        "Multi-Head Attention": 6,
        "Transformer": 10,
        "Markov Decision Process": 8,
    }

    FALLBACK_HOURS = 5

    @classmethod
    def _hours(cls, concept):
        """Study hours for a concept: the curated value when it is a finite positive number, otherwise the logged fallback."""
        hours = cls.STUDY_TIME.get(concept, cls.FALLBACK_HOURS)
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not math.isfinite(hours) or hours <= 0:
            logger.warning("invalid study hours %r for %s: using the fallback of %s", hours, concept, cls.FALLBACK_HOURS)
            return cls.FALLBACK_HOURS
        return hours

    def generate(
        self,
        paper: Paper,
    ) -> Paper:

        paper.learning_plan.clear()

        missing = [

            prerequisite

            for prerequisite in paper.missing_prerequisites

            if not prerequisite.satisfied
        ]

        # A concept listed twice is one thing to study: keep its first entry so its hours are not counted twice.
        missing = list({prerequisite.concept: prerequisite for prerequisite in reversed(missing)}.values())[::-1]

        missing.sort(

            # Concepts without a curated position share the fallback position, so the name breaks the tie deterministically.
            key=lambda prerequisite: (

                self.STUDY_ORDER.get(
                    prerequisite.concept,
                    999,
                ),

                prerequisite.concept,
            )
        )

        # A concept missing from the order or time tables gets the fallback position and 5 hours: that is a placeholder, not a
        # curated estimate, so the gap is logged instead of passing silently.
        uncurated = sorted({p.concept for p in missing if p.concept not in self.STUDY_ORDER or p.concept not in self.STUDY_TIME})

        if uncurated:

            logger.warning("study plan uses fallback order and hours for concepts without a curated entry: %s", ", ".join(uncurated))

        for index, prerequisite in enumerate(
            missing,
            start=1,
        ):

            paper.learning_plan.append(

                LearningStep(

                    order=index,

                    concept=prerequisite.concept,

                    estimated_hours=self._hours(prerequisite.concept),
                )
            )

        return paper
