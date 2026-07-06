from dataclasses import dataclass, field

from backend.ingestion import (
    RawDocument,
    DocumentMetadata,
    RawPage,
)
from .concept import DetectedConcept
from .knowledge_graph import KnowledgeGraph


@dataclass
class PaperSection:
    title: str
    content: str


@dataclass
class Equation:
    equation_id: int
    expression: str
    section: str


@dataclass
class PaperFigure:
    figure_id: int
    page_number: int
    image_index: int
    width: int
    height: int


@dataclass
class PaperTable:
    table_id: int
    page_number: int
    rows: list[list[str]]


@dataclass
class PaperReference:
    reference_number: int
    raw_text: str


@dataclass
class Paragraph:
    paragraph_id: int
    section_title: str
    content: str


@dataclass
class PaperAlgorithm:
    algorithm_id: int
    title: str
    content: str
    section: str


@dataclass
class ConceptExplanation:
    concept: str
    definition: str
    difficulty: str


@dataclass
class Prerequisite:
    concept: str
    reason: str
    confidence: float


@dataclass
class MissingPrerequisite:
    concept: str
    satisfied: bool
    reason: str


@dataclass
class Paper:
    source_path: str

    metadata: DocumentMetadata

    pages: list[RawPage] = field(default_factory=list)

    sections: list[PaperSection] = field(default_factory=list)

    equations: list[Equation] = field(default_factory=list)

    figures: list[PaperFigure] = field(default_factory=list)

    tables: list[PaperTable] = field(default_factory=list)

    references: list[PaperReference] = field(default_factory=list)

    paragraphs: list[Paragraph] = field(default_factory=list)

    algorithms: list[PaperAlgorithm] = field(default_factory=list)

    concepts: list[DetectedConcept] = field(default_factory=list)

    knowledge_graph: KnowledgeGraph = field(
        default_factory=KnowledgeGraph
    )

    concept_explanations: list[
        ConceptExplanation
    ] = field(default_factory=list)

    prerequisites: list[
        Prerequisite
    ] = field(default_factory=list)

    missing_prerequisites: list[
        MissingPrerequisite
    ] = field(default_factory=list)
