from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class ExperimentNavigator:
    """
    Navigates experiments extracted from
    research papers.
    """

    def navigate(

        self,

        paper: Paper,

        experiment_id: str,

    ) -> NavigationResult:

        for experiment in paper.experiments:

            if (

                str(experiment.experiment_id)

                == experiment_id.strip()

            ):

                return NavigationResult(

                    target="experiment",

                    title=experiment.title,

                    summary=experiment.description,

                    metadata={

                        "section":
                            experiment.section,

                        "dataset": None,

                        "metric": None,
                    },
                )

        raise ValueError(

            f"Experiment '{experiment_id}' "

            "not found."
        )
