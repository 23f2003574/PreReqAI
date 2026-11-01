import requests

from backend.ingestion import (
    ResearchSource,
)

from backend.ingestion.arxiv_resolver import (
    ArxivResolver,
)


class _Reply:
    content = b"%PDF-1.4 stand-in\n%%EOF"

    def raise_for_status(self):
        pass


def test_arxiv_download(tmp_path, monkeypatch):
    """Offline: the download is faked, so the test needs no network and writes nothing outside tmp_path."""

    requested = []
    monkeypatch.setattr(ArxivResolver, "CACHE_DIRECTORY", tmp_path / "arxiv")
    monkeypatch.setattr(requests, "get", lambda url, timeout: requested.append(url) or _Reply())

    pdf = ArxivResolver().resolve(

        ResearchSource(
            source_type="arxiv",
            identifier="1706.03762",
            original_input="https://arxiv.org/abs/1706.03762",
        )
    )

    assert pdf.endswith(".pdf")
    assert requested == ["https://arxiv.org/pdf/1706.03762.pdf"]
    assert open(pdf, "rb").read().startswith(b"%PDF")
