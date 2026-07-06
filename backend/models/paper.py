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
class LearningStep:
    order: int
    concept: str
    estimated_hours: int


@dataclass
class PaperDifficulty:
    level: str
    score: float
    explanation: str


@dataclass
class StudyTimeEstimate:
    total_hours: int
    recommended_days: int
    average_hours_per_day: float


@dataclass
class DifficultyExplanation:
    title: str
    description: str


@dataclass
class StudyAction:
    priority: int
    title: str
    description: str


@dataclass
class LearningResource:
    concept: str
    title: str
    provider: str
    url: str
    estimated_hours: int


@dataclass
class RoadmapStep:
    step: int
    concept: str
    resource_title: str
    provider: str
    estimated_hours: int


@dataclass
class StudyProgress:
    concept: str
    completed: bool
    progress_percent: int


@dataclass
class PaperReadiness:
    progress_percent: int
    ready_to_read: bool
    completed_concepts: int
    total_concepts: int
    status: str


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

    learning_plan: list[
        LearningStep
    ] = field(default_factory=list)

    difficulty: PaperDifficulty | None = None

    study_time: StudyTimeEstimate | None = None

    difficulty_explanations: list[
        DifficultyExplanation
    ] = field(default_factory=list)

    study_actions: list[
        StudyAction
    ] = field(default_factory=list)

    learning_resources: list[
        LearningResource
    ] = field(default_factory=list)

    study_roadmap: list[
        RoadmapStep
    ] = field(default_factory=list)

    study_progress: list[
        StudyProgress
    ] = field(default_factory=list)

    readiness: PaperReadiness | None = None
