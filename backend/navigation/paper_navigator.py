from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)

from .navigation_target import (
    NavigationTarget,
)


class PaperNavigator:
    """
    Central navigation engine for
    research papers.
    """

    def navigate(

        self,

        paper: Paper,

        target: NavigationTarget,

        query: str,

    ) -> NavigationResult:

        return NavigationResult(

            target=target.value,

            title=query,

            summary=(
                "Navigation support "
                "will be implemented "
                "by specialized navigators."
            ),
        )
