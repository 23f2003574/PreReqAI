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

from backend.resources import (
    LearningResourceRecommender,
)

from backend.resources import (
    StudyRoadmapGenerator,
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

        self.algorithm_extractor = (
            AlgorithmExtractor()
        )

        self.paragraph_segmenter = ParagraphSegmenter()

        self.concept_detector = RuleBasedConceptDetector()

        self.prerequisite_detector = (
            PrerequisiteDetector()
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
    ) -> dict:

        source = self.source_detector.detect(
            file_path,
        )

        pdf_path = self.source_resolver.resolve(
            source,
        )

        document = self.ingestion.ingest(
            pdf_path,
        )

        paper = self.section_parser.parse(document)

        paper = self.equation_extractor.extract(paper)

        paper = self.figure_extractor.extract(
            pdf_path,
            paper,
        )

        paper = self.table_extractor.extract(
            pdf_path,
            paper,
        )

        paper = self.reference_extractor.extract(
            paper,
        )

        paper = self.algorithm_extractor.extract(
            paper,
        )

        paper = self.paragraph_segmenter.segment(
            paper,
        )

        paper = self.concept_detector.detect(
            paper,
        )

        paper = self.prerequisite_detector.detect(
            paper,
        )

        paper = (
            self.missing_prerequisite_analyzer
            .analyze(paper)
        )

        paper = (
            self.learning_planner.generate(
                paper,
            )
        )

        paper = (
            self.difficulty_engine.assess(
                paper,
            )
        )

        paper = (
            self.difficulty_explanation_engine
            .explain(paper)
        )

        paper = (
            self.study_time_estimator.estimate(
                paper,
            )
        )

        paper = (
            self.study_action_generator.generate(
                paper,
            )
        )

        paper = (
            self.resource_recommender.recommend(
                paper,
            )
        )

        paper = (
            self.study_roadmap_generator.generate(
                paper,
            )
        )

        paper = self.explanation_engine.explain(
            paper,
        )

        paper = self.graph_builder.build(
            paper,
        )

        paper = self.relationship_builder.build(
            paper,
        )

        paper = (
            self.paragraph_relationship_builder
            .build(paper)
        )

        return self.report_generator.generate(
            paper,
        )
