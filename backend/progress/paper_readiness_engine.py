from backend.models import (
    Paper,
    PaperReadiness,
)


class PaperReadinessEngine:
    """
    Evaluates whether a learner is ready
    to begin reading the research paper.
    """

    def evaluate(
        self,
        paper: Paper,
    ) -> Paper:

        total = len(
            paper.study_progress
        )

        completed = sum(

            progress.completed

            for progress
            in paper.study_progress
        )

        percent = 100

        if total:

            percent = round(
                completed / total * 100
            )

        ready = percent >= 100

        paper.readiness = PaperReadiness(

            progress_percent=percent,

            ready_to_read=ready,

            completed_concepts=completed,

            total_concepts=total,

            status=(
                "Ready to Read"
                if ready
                else "Preparation Required"
            ),
        )

        return paper
