import re

from dataclasses import dataclass, field

from .scientific_section_parser import ParsedPaper


DISPLAY_EQUATION_PATTERN = re.compile(
    r"^\s*.+?=\s*.+$",
    re.MULTILINE,
)


@dataclass
class Equation:
    equation_id: int
    expression: str
    section: str


@dataclass
class ParsedPaperWithEquations:
    parsed_paper: ParsedPaper
    equations: list[Equation] = field(default_factory=list)


class EquationExtractor:
    """
    Extracts display-style mathematical equations
    from each detected paper section.

    Initial implementation intentionally targets
    common research-paper equation layouts.
    """

    def extract(
        self,
        parsed_paper: ParsedPaper,
    ) -> ParsedPaperWithEquations:

        equations = []

        equation_counter = 1

        for section in parsed_paper.sections:

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

        return ParsedPaperWithEquations(
            parsed_paper=parsed_paper,
            equations=equations,
        )
