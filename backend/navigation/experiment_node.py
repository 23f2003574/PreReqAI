from dataclasses import dataclass


@dataclass
class ExperimentNode:
    """
    Represents a navigable experiment
    inside a research paper.
    """

    identifier: str

    title: str

    description: str

    dataset: str

    metric: str

    section: str

    page: int
