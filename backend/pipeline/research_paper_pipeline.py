from backend.ingestion import PDFIngestionEngine

from backend.ingestion import (
    ResearchSourceDetector,
)

from backend.parsing import (
    ScientificSectionParser,
    EquationExtractor,
    FigureExtractor,
    TableExtractor,
    ReferenceExtractor,
    ParagraphSegmenter,
)

from backend.concepts import (
    RuleBasedConceptDetector,
)

from backend.serialization import (
    PaperSerializer,
)


class ResearchPaperPipeline:
    """
    Executes the complete Phase 1 processing
    pipeline for an uploaded research paper.
    """

    def __init__(self):

        self.ingestion = PDFIngestionEngine()

        self.source_detector = ResearchSourceDetector()

        self.section_parser = ScientificSectionParser()

        self.equation_extractor = EquationExtractor()

        self.figure_extractor = FigureExtractor()

        self.table_extractor = TableExtractor()

        self.reference_extractor = ReferenceExtractor()

        self.paragraph_segmenter = ParagraphSegmenter()

        self.concept_detector = RuleBasedConceptDetector()

        self.serializer = PaperSerializer()

    def run(
        self,
        file_path: str,
    ) -> dict:

        source = self.source_detector.detect(
            file_path,
        )

        if source.source_type != "pdf":

            raise NotImplementedError(
                f"{source.source_type} ingestion will be implemented in upcoming commits."
            )

        document = self.ingestion.ingest(
            source.identifier,
        )

        paper = self.section_parser.parse(document)

        paper = self.equation_extractor.extract(paper)

        paper = self.figure_extractor.extract(
            file_path,
            paper,
        )

        paper = self.table_extractor.extract(
            file_path,
            paper,
        )

        paper = self.reference_extractor.extract(
            paper,
        )

        paper = self.paragraph_segmenter.segment(
            paper,
        )

        paper = self.concept_detector.detect(
            paper,
        )

        return self.serializer.serialize(
            paper,
        )
