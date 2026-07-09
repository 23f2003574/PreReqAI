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


class PaperNavigator:
    """
    Central navigation engine for
    research papers.
    """

    def __init__(self):

        self.section_navigator = (

            SectionNavigator()
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

        raise NotImplementedError(

            f"{target.value} navigation "

            "is not implemented."
        )
