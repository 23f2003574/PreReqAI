from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class EquationNavigator:
    """
    Navigates through equations extracted
    from a research paper.
    """

    def navigate(

        self,

        paper: Paper,

        equation_id: str,

    ) -> NavigationResult:

        for equation in paper.equations:

            if (

                str(equation.equation_id)

                == equation_id.strip()

            ):

                return NavigationResult(

                    target="equation",

                    title=f"Equation {equation.equation_id}",

                    summary=equation.expression,

                    metadata={

                        "expression":
                            equation.expression,

                        "section":
                            equation.section,
                    },
                )

        raise ValueError(

            f"Equation '{equation_id}' "

            "not found."
        )
