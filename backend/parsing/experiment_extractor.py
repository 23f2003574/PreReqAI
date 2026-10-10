from backend.models import Paper, Experiment


EXPERIMENT_SECTION_TITLES = {
    "experiments",
    "experimental setup",
    "results",
}


class ExperimentExtractor:
    """
    Promotes sections that describe experimental
    evaluation (Experiments/Experimental Setup/
    Results) into first-class Experiment objects.

    Dataset/metric extraction requires deeper
    semantic parsing than this stage performs and
    is intentionally left to a future commit.
    """

    def extract(
        self,
        paper: Paper,
    ) -> Paper:

        experiments = []

        experiment_counter = 1

        for section in paper.sections:

            if (
                section.title.lower()
                not in EXPERIMENT_SECTION_TITLES
            ):
                continue

            experiments.append(
                Experiment(
                    experiment_id=experiment_counter,
                    title=section.title,
                    description=section.content,
                    section=section.title,
                )
            )

            experiment_counter += 1

        paper.experiments = experiments

        return paper
