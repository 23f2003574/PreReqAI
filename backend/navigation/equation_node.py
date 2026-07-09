from dataclasses import dataclass


@dataclass
class EquationNode:
    """
    Represents a navigable mathematical
    equation.
    """

    identifier: str

    latex: str

    description: str

    section: str

    page: int
