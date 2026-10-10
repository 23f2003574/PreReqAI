from backend.reporting import (
    LearningReportGenerator,
)

from backend.models import (
    Paper,
)

from backend.ingestion import (
    DocumentMetadata,
)


def test_learning_report_creation():

    paper = Paper(
        source_path="sample.pdf",
        metadata=DocumentMetadata(
            title="Sample Paper",
            author="Sample Author",
            subject="",
            keywords="",
            creator="",
            producer="",
            page_count=1,
        ),
    )

    report = (
        LearningReportGenerator()
        .generate(paper)
    )

    assert isinstance(
        report,
        dict,
    )
