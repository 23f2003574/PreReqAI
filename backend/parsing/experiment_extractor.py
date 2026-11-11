import re

from backend.models import Paper, Experiment


EXPERIMENT_SECTION_TITLES = {
    "experiments",
    "experimental setup",
    "experimental results",
    "experimental evaluation",
    "empirical evaluation",
    "experiments and results",
    "results",
    "results and discussion",
    "results and analysis",
    "evaluation results",
}

# Section titles keep the heading's number ("4 Experiments", "3.2 Experimental Setup", "IV. Results") and an optional colon.
_NUMBER_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+")


def _bare_title(title: str) -> str:
    return _NUMBER_PREFIX.sub("", title.strip()).rstrip(":").strip().lower()


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
                _bare_title(section.title)
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
