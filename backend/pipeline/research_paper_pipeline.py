from dataclasses import dataclass, field
from time import perf_counter

from backend.ingestion import PDFIngestionEngine

from backend.ingestion import (
    ResearchSourceDetector,
)

from backend.ingestion import (
    ResearchSourceResolver,
)

from backend.ingestion import (
    ResearchMetadataResolver,
)

from backend.parsing import (
    ScientificSectionParser,
    EquationExtractor,
    FigureExtractor,
    TableExtractor,
    ReferenceExtractor,
    CitationExtractor,
    ExperimentExtractor,
    RelatedPaperExtractor,
    ParagraphSegmenter,
    AlgorithmExtractor,
)

from backend.concepts import (
    RuleBasedConceptDetector,
)

from backend.concepts import (
    ConceptExplanationEngine,
)

from backend.prerequisites import (
    PrerequisiteDetector,
)

from backend.prerequisites import (
    MissingPrerequisiteAnalyzer,
)

from backend.prerequisites import (
    PrerequisiteLearningPlanner,
)

from backend.prerequisites import (
    DifficultyAssessmentEngine,
)

from backend.prerequisites import (
    StudyTimeEstimator,
)

from backend.prerequisites import (
    DifficultyExplanationEngine,
)

from backend.prerequisites import (
    StudyActionPlanGenerator,
)

from backend.prerequisites import (
    PrerequisiteJustificationEngine,
)

from backend.resources import (
    LearningResourceRecommender,
)

from backend.resources import (
    StudyRoadmapGenerator,
)

from backend.progress import (
    StudyProgressTracker,
)

from backend.progress import (
    PaperReadinessEngine,
)

from backend.graph import (
    KnowledgeGraphBuilder,
)

from backend.graph import (
    ConceptRelationshipBuilder,
)

from backend.graph import (
    ParagraphConceptRelationshipBuilder,
)

from backend.graph import (
    LearningPathGenerator,
)

from backend.serialization import (
    PaperSerializer,
)

from backend.reporting import (
    LearningReportGenerator,
)


from backend.models import Paper


class PipelineCancelled(Exception):
    """Raised by ResearchPaperPipeline.run() when its should_cancel callback
    reported True. Cancellation is checked between stages (a running stage is
    not interrupted), so nothing is left half-built: no result is returned."""


class _StageTimer:
    """Wall-clock seconds per pipeline stage: mark(name) records the time since
    the previous mark (or the start) under that stage name, then checks for
    cancellation before the next stage starts. In-memory only."""

    def __init__(self, should_cancel=None):

        self.stages = {}

        self.current = None

        self._should_cancel = should_cancel

        self._last = perf_counter()

    def check_cancelled(self):

        if self._should_cancel is not None and self._should_cancel():

            raise PipelineCancelled("analysis cancelled")

    def mark(self, name: str, final: bool = False):

        now = perf_counter()

        self.stages[name] = round(self.stages.get(name, 0.0) + (now - self._last), 6)

        self._last = now

        if not final:

            self.check_cancelled()


@dataclass
class PipelineResult:

    paper: Paper

    report: dict

    timings: dict = field(default_factory=dict)


# Every stage run() executes, in order: (stage, component attribute, method,
# inputs read from the run's context, output written back to it). A stage gets
# only what an earlier stage (or the caller: "file_path") produced.
_STAGES = (
    ("source_detector", "source_detector", "detect", ("file_path",), "source"),
    ("source_resolver", "source_resolver", "resolve", ("source",), "pdf_path"),
    ("ingestion", "ingestion", "ingest", ("pdf_path",), "document"),
    ("section_parser", "section_parser", "parse", ("document",), "paper"),
    ("equation_extractor", "equation_extractor", "extract", ("paper",), "paper"),
    ("figure_extractor", "figure_extractor", "extract", ("pdf_path", "paper"), "paper"),
    ("table_extractor", "table_extractor", "extract", ("pdf_path", "paper"), "paper"),
    ("reference_extractor", "reference_extractor", "extract", ("paper",), "paper"),
    ("related_paper_extractor", "related_paper_extractor", "extract", ("paper",), "paper"),
    ("algorithm_extractor", "algorithm_extractor", "extract", ("paper",), "paper"),
    ("experiment_extractor", "experiment_extractor", "extract", ("paper",), "paper"),
    ("paragraph_segmenter", "paragraph_segmenter", "segment", ("paper",), "paper"),
    ("citation_extractor", "citation_extractor", "extract", ("paper",), "paper"),
    ("concept_detector", "concept_detector", "detect", ("paper",), "paper"),
    ("prerequisite_detector", "prerequisite_detector", "detect", ("paper",), "paper"),
    ("justification_engine", "justification_engine", "justify", ("paper",), "paper"),
    ("missing_prerequisite_analyzer", "missing_prerequisite_analyzer", "analyze", ("paper",), "paper"),
    ("learning_planner", "learning_planner", "generate", ("paper",), "paper"),
    ("difficulty_engine", "difficulty_engine", "assess", ("paper",), "paper"),
    ("difficulty_explanation_engine", "difficulty_explanation_engine", "explain", ("paper",), "paper"),
    ("study_time_estimator", "study_time_estimator", "estimate", ("paper",), "paper"),
    ("study_action_generator", "study_action_generator", "generate", ("paper",), "paper"),
    ("resource_recommender", "resource_recommender", "recommend", ("paper",), "paper"),
    ("study_roadmap_generator", "study_roadmap_generator", "generate", ("paper",), "paper"),
    ("progress_tracker", "progress_tracker", "initialize", ("paper",), "paper"),
    ("readiness_engine", "readiness_engine", "evaluate", ("paper",), "paper"),
    ("explanation_engine", "explanation_engine", "explain", ("paper",), "paper"),
    ("graph_builder", "graph_builder", "build", ("paper",), "paper"),
    ("relationship_builder", "relationship_builder", "build", ("paper",), "paper"),
    ("paragraph_relationship_builder", "paragraph_relationship_builder", "build", ("paper",), "paper"),
    ("report_generator", "report_generator", "generate", ("paper",), "report"),
)

# What the stages writing these context keys must return: a stage that returns
# anything else (e.g. None from a missing return) fails at that stage instead of
# handing a broken value to the stages after it.
_STAGE_OUTPUT_TYPES = {"paper": Paper, "report": dict}

# A result is complete only if all of these were timed (a test pins this tuple
# to what run() really records).
PIPELINE_STAGES = tuple(stage for stage, *_ in _STAGES)


class ResearchPaperPipeline:
    """
    Executes the complete Phase 1 processing
    pipeline for an uploaded research paper.
    """

    def __init__(self):

        self.ingestion = PDFIngestionEngine()

        self.source_detector = ResearchSourceDetector()

        self.source_resolver = ResearchSourceResolver()

        self.metadata_resolver = (
            ResearchMetadataResolver()
        )

        self.section_parser = ScientificSectionParser()

        self.equation_extractor = EquationExtractor()

        self.figure_extractor = FigureExtractor()

        self.table_extractor = TableExtractor()

        self.reference_extractor = ReferenceExtractor()

        self.related_paper_extractor = (
            RelatedPaperExtractor()
        )

        self.citation_extractor = CitationExtractor()

        self.algorithm_extractor = (
            AlgorithmExtractor()
        )

        self.experiment_extractor = (
            ExperimentExtractor()
        )

        self.paragraph_segmenter = ParagraphSegmenter()

        self.concept_detector = RuleBasedConceptDetector()

        self.prerequisite_detector = (
            PrerequisiteDetector()
        )

        self.justification_engine = (
            PrerequisiteJustificationEngine()
        )

        self.missing_prerequisite_analyzer = (
            MissingPrerequisiteAnalyzer()
        )

        self.learning_planner = (
            PrerequisiteLearningPlanner()
        )

        self.difficulty_engine = (
            DifficultyAssessmentEngine()
        )

        self.study_time_estimator = (
            StudyTimeEstimator()
        )

        self.difficulty_explanation_engine = (
            DifficultyExplanationEngine()
        )

        self.study_action_generator = (
            StudyActionPlanGenerator()
        )

        self.resource_recommender = (
            LearningResourceRecommender()
        )

        self.study_roadmap_generator = (
            StudyRoadmapGenerator()
        )

        self.progress_tracker = (
            StudyProgressTracker()
        )

        self.readiness_engine = (
            PaperReadinessEngine()
        )

        self.explanation_engine = (
            ConceptExplanationEngine()
        )

        self.graph_builder = (
            KnowledgeGraphBuilder()
        )

        self.relationship_builder = (
            ConceptRelationshipBuilder()
        )

        self.paragraph_relationship_builder = (
            ParagraphConceptRelationshipBuilder()
        )

        self.learning_path_generator = (
            LearningPathGenerator()
        )

        self.serializer = PaperSerializer()

        self.report_generator = (
            LearningReportGenerator()
        )

    def run(
        self,
        file_path: str,
        should_cancel=None,
    ) -> PipelineResult:

        timer = _StageTimer(should_cancel)

        try:

            timer.check_cancelled()

            return self._run(file_path, timer)

        except Exception as exc:

            # What finished before the failure, for diagnostics; the exception itself is unchanged.
            exc.stage_timings = dict(timer.stages)

            # The stage that was running when it failed (None: between stages, e.g. cancelled).
            exc.failed_stage = timer.current

            raise

    def _run(
        self,
        file_path: str,
        timer: "_StageTimer",
    ) -> PipelineResult:

        context = {"file_path": file_path}

        for stage, component, method, inputs, output in _STAGES:

            timer.current = stage

            step = getattr(getattr(self, component), method)

            value = step(*(context[name] for name in inputs))

            expected = _STAGE_OUTPUT_TYPES.get(output, object)

            if value is None or not isinstance(value, expected):

                raise TypeError(f"stage {stage} returned {type(value).__name__}, expected {expected.__name__}")

            context[output] = value

            timer.current = None  # done: a cancellation from here on is not this stage's failure

            timer.mark(stage, final=stage == PIPELINE_STAGES[-1])

        return PipelineResult(
            paper=context["paper"],
            report=context["report"],
            timings=timer.stages,
        )
