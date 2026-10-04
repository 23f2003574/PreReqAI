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

            raise

    def _run(
        self,
        file_path: str,
        timer: "_StageTimer",
    ) -> PipelineResult:

        source = self.source_detector.detect(
            file_path,
        )

        timer.mark("source_detector")

        pdf_path = self.source_resolver.resolve(
            source,
        )

        timer.mark("source_resolver")

        document = self.ingestion.ingest(
            pdf_path,
        )

        timer.mark("ingestion")

        paper = self.section_parser.parse(document)

        timer.mark("section_parser")

        paper = self.equation_extractor.extract(paper)

        timer.mark("equation_extractor")

        paper = self.figure_extractor.extract(
            pdf_path,
            paper,
        )

        timer.mark("figure_extractor")

        paper = self.table_extractor.extract(
            pdf_path,
            paper,
        )

        timer.mark("table_extractor")

        paper = self.reference_extractor.extract(
            paper,
        )

        timer.mark("reference_extractor")

        paper = self.related_paper_extractor.extract(
            paper,
        )

        timer.mark("related_paper_extractor")

        paper = self.algorithm_extractor.extract(
            paper,
        )

        timer.mark("algorithm_extractor")

        paper = self.experiment_extractor.extract(
            paper,
        )

        timer.mark("experiment_extractor")

        paper = self.paragraph_segmenter.segment(
            paper,
        )

        timer.mark("paragraph_segmenter")

        paper = self.citation_extractor.extract(
            paper,
        )

        timer.mark("citation_extractor")

        paper = self.concept_detector.detect(
            paper,
        )

        timer.mark("concept_detector")

        paper = self.prerequisite_detector.detect(
            paper,
        )

        timer.mark("prerequisite_detector")

        paper = (
            self.justification_engine.justify(
                paper,
            )
        )

        timer.mark("justification_engine")

        paper = (
            self.missing_prerequisite_analyzer
            .analyze(paper)
        )

        timer.mark("missing_prerequisite_analyzer")

        paper = (
            self.learning_planner.generate(
                paper,
            )
        )

        timer.mark("learning_planner")

        paper = (
            self.difficulty_engine.assess(
                paper,
            )
        )

        timer.mark("difficulty_engine")

        paper = (
            self.difficulty_explanation_engine
            .explain(paper)
        )

        timer.mark("difficulty_explanation_engine")

        paper = (
            self.study_time_estimator.estimate(
                paper,
            )
        )

        timer.mark("study_time_estimator")

        paper = (
            self.study_action_generator.generate(
                paper,
            )
        )

        timer.mark("study_action_generator")

        paper = (
            self.resource_recommender.recommend(
                paper,
            )
        )

        timer.mark("resource_recommender")

        paper = (
            self.study_roadmap_generator.generate(
                paper,
            )
        )

        timer.mark("study_roadmap_generator")

        paper = (
            self.progress_tracker.initialize(
                paper,
            )
        )

        timer.mark("progress_tracker")

        paper = (
            self.readiness_engine.evaluate(
                paper,
            )
        )

        timer.mark("readiness_engine")

        paper = self.explanation_engine.explain(
            paper,
        )

        timer.mark("explanation_engine")

        paper = self.graph_builder.build(
            paper,
        )

        timer.mark("graph_builder")

        paper = self.relationship_builder.build(
            paper,
        )

        timer.mark("relationship_builder")

        paper = (
            self.paragraph_relationship_builder
            .build(paper)
        )

        timer.mark("paragraph_relationship_builder")

        report = self.report_generator.generate(
            paper,
        )

        timer.mark("report_generator", final=True)

        return PipelineResult(
            paper=paper,
            report=report,
            timings=timer.stages,
        )
