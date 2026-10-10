from backend.session import (
    LearningGap,
    LearningSession,
)


class LearningGapAnalyzer:
    """
    Tracks conceptual weaknesses across
    tutoring interactions.
    """

    def analyze(
        self,
        session: LearningSession,
    ):

        gaps = {}

        for turn in session.conversation_history:

            if turn["type"] != "quiz":

                continue

            concept = turn["concept"]

            if concept not in gaps:

                gaps[concept] = LearningGap(

                    concept=concept,

                    incorrect_attempts=0,

                    mastery=1.0,
                )

            if not turn["correct"]:

                gaps[concept].incorrect_attempts += 1

        for gap in gaps.values():

            gap.mastery = max(

                0.0,

                1.0 - gap.incorrect_attempts * 0.2,
            )

        session.learning_gaps = list(
            gaps.values()
        )

        return session.learning_gaps
