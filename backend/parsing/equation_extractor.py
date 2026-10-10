import re

from backend.models import Paper, Equation


DISPLAY_EQUATION_PATTERN = re.compile(
    r"^\s*.+?=\s*.+$",
    re.MULTILINE,
)


class EquationExtractor:
    """
    Extracts display-style mathematical equations
    from each detected paper section.

    Initial implementation intentionally targets
    common research-paper equation layouts.
    """

    def extract(self, paper: Paper) -> Paper:

        equations = []

        equation_counter = 1

        for section in paper.sections:

            matches = DISPLAY_EQUATION_PATTERN.findall(
                section.content
            )

            for match in matches:

                equations.append(
                    Equation(
                        equation_id=equation_counter,
                        expression=match.strip(),
                        section=section.title,
                    )
                )

                equation_counter += 1

        paper.equations = equations

        return paper
