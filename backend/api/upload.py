from backend.pipeline import (
    ResearchPaperPipeline,
)


def handle_pdf_upload(
    file_path: str,
):

    pipeline = ResearchPaperPipeline()

    return pipeline.run(file_path)
