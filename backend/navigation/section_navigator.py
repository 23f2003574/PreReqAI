from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class SectionNavigator:
    """
    Navigates through the structural
    sections of a research paper.
    """

    def navigate(

        self,

        paper: Paper,

        section_name: str,

    ) -> NavigationResult:

        for section in paper.sections:

            if (

                section.title.lower()

                == section_name.lower()

            ):

                return NavigationResult(

                    target="section",

                    title=section.title,

                    summary=section.content,
                )

        raise ValueError(

            f"Section '{section_name}' "

            "not found."
        )
