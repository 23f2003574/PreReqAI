from dataclasses import dataclass, field

from backend.ingestion import (
    RawDocument,
    DocumentMetadata,
    RawPage,
)
from backend.interaction import ResearchObject
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
class Citation:
    citation_id: int
    reference_number: int
    context: str
    section: str


@dataclass
class Experiment:
    experiment_id: int
    title: str
    description: str
    section: str


@dataclass
class RelatedPaper:
    reference_number: int
    title: str
    authors: list[str]
    year: int | None
    relationship: str
    similarity_score: float | None


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
    confidence: float  # the share of the paper's rule-bearing concepts that need this prerequisite (see PrerequisiteDetector)
    importance: str = ""  # "essential" or "supporting"
    importance_reason: str = ""
    dependent_mentions: int = 0  # mentions in the paper of the concepts that need it (concepts without a count add nothing)
    evidence: list = field(default_factory=list)  # [{concept, relation: direct|indirect, occurrences: int|None}] per dependent concept
    evidence_note: str = ""  # what the evidence does and does not show


@dataclass
class MissingPrerequisite:
    concept: str
    satisfied: bool
    reason: str
    status: str = ""  # covered | mentioned_only | not_mentioned | unknown (no mention count available)
    mentions: "int | None" = None  # the paper's mentions of this concept; None when no count is available


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
    daily_hours: float = 3.0  # the learner's available hours per day the schedule was built for
    schedule: list = field(default_factory=list)  # [{day, hours, items: [{concept, hours}]}]; sessions saved earlier lack it


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
class PrerequisiteJustification:
    concept: str
    justification: str


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

    citations: list[Citation] = field(default_factory=list)

    experiments: list[Experiment] = field(default_factory=list)

    related_papers: list[RelatedPaper] = field(default_factory=list)

    paragraphs: list[Paragraph] = field(default_factory=list)

    algorithms: list[PaperAlgorithm] = field(default_factory=list)

    concepts: list[DetectedConcept] = field(default_factory=list)

    # Diagnostic only: acronym-defined terms the concept registry does not know (never treated as detected concepts).
    unrecognised_terms: list[str] = field(default_factory=list)

    # Diagnostic only: registered vs detected concept counts for this document (see concept_detection_coverage).
    concept_coverage: dict = field(default_factory=dict)

    knowledge_graph: KnowledgeGraph = field(
        default_factory=KnowledgeGraph
    )

    concept_explanations: list[
        ConceptExplanation
    ] = field(default_factory=list)

    prerequisites: list[
        Prerequisite
    ] = field(default_factory=list)

    # Diagnostic only: detected concepts with no entry at all in the prerequisite rules. That means "unsupported", not
    # "needs nothing" (a rule with an empty list is the explicit way to say the latter).
    concepts_without_rules: list[str] = field(default_factory=list)

    missing_prerequisites: list[
        MissingPrerequisite
    ] = field(default_factory=list)

    learning_plan: list[
        LearningStep
    ] = field(default_factory=list)

    difficulty: PaperDifficulty | None = None

    study_time: StudyTimeEstimate | None = None

    hours_per_day: float = 3.0  # the learner's daily study time; sessions saved before it existed read the class default

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

    # Concepts studied before being marked known: dropped from the plan, restored if the learner un-marks known.
    studied_while_known: list[str] = field(default_factory=list)

    readiness: PaperReadiness | None = None

    prerequisite_justifications: list[
        PrerequisiteJustification
    ] = field(default_factory=list)

    interactive_objects: list[
        ResearchObject
    ] = field(default_factory=list)
