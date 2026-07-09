from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)

from .navigation_target import (
    NavigationTarget,
)

from .section_navigator import (
    SectionNavigator,
)

from .concept_navigator import (
    ConceptNavigator,
)

from .equation_navigator import (
    EquationNavigator,
)

from .figure_navigator import (
    FigureNavigator,
)

from .citation_navigator import (
    CitationNavigator,
)

from .reference_navigator import (
    ReferenceNavigator,
)

from .experiment_navigator import (
    ExperimentNavigator,
)

from .knowledge_graph_navigator import (
    KnowledgeGraphNavigator,
)


class PaperNavigator:
    """
    Central navigation engine for
    research papers.
    """

    def __init__(self):

        self.section_navigator = (

            SectionNavigator()
        )

        self.concept_navigator = (

            ConceptNavigator()
        )

        self.equation_navigator = (

            EquationNavigator()
        )

        self.figure_navigator = (

            FigureNavigator()
        )

        self.citation_navigator = (

            CitationNavigator()
        )

        self.reference_navigator = (

            ReferenceNavigator()
        )

        self.experiment_navigator = (

            ExperimentNavigator()
        )

        self.knowledge_graph_navigator = (

            KnowledgeGraphNavigator()
        )

    def navigate(

        self,

        paper: Paper,

        target: NavigationTarget,

        query: str,

    ) -> NavigationResult:

        if target == NavigationTarget.SECTION:

            return (
                self.section_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.CONCEPT:

            return (
                self.concept_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.EQUATION:

            return (
                self.equation_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.FIGURE:

            return (
                self.figure_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.CITATION:

            return (
                self.citation_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.REFERENCE:

            return (
                self.reference_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.EXPERIMENT:

            return (
                self.experiment_navigator.navigate(

                    paper,

                    query,
                )
            )

        if target == NavigationTarget.KNOWLEDGE_GRAPH:

            return (
                self.knowledge_graph_navigator.navigate(

                    paper,

                    query,
                )
            )

        raise NotImplementedError(

            f"{target.value} navigation "

            "is not implemented."
        )
