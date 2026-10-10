from enum import Enum


class NavigationTarget(str, Enum):

    SECTION = "section"

    CONCEPT = "concept"

    EQUATION = "equation"

    FIGURE = "figure"

    EXPERIMENT = "experiment"

    CITATION = "citation"

    REFERENCE = "reference"

    KNOWLEDGE_GRAPH = "knowledge_graph"

    RELATED_PAPER = "related_paper"
