from enum import Enum


class ResearchObjectType(str, Enum):

    CONCEPT = "concept"

    EQUATION = "equation"

    FIGURE = "figure"

    EXPERIMENT = "experiment"

    SECTION = "section"

    REFERENCE = "reference"

    CITATION = "citation"

    RELATED_PAPER = "related_paper"
