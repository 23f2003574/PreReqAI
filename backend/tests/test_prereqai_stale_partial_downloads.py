"""A download interrupted by a hard kill leaves its `.part` file behind (the in-process cleanup never ran). The next stored
download removes such stale leftovers, but never a recent `.part` that may belong to a download still in progress."""
import os
import time

import pytest

from backend.ingestion.arxiv_resolver import ArxivResolver

pytestmark = pytest.mark.prereqai

PDF = b"%PDF-1.4 whole\n%%EOF"


def test_stale_partial_files_are_removed_when_the_next_download_is_stored(tmp_path):
    stale = tmp_path / "1706.03762.pdf.99999.1.part"
    live = tmp_path / "2001.00001.pdf.88888.2.part"
    stale.write_bytes(b"%PDF-1.4 cut")
    live.write_bytes(b"%PDF-1.4 in progress")
    old = time.time() - ArxivResolver.STALE_PARTIAL_SECONDS - 60
    os.utime(stale, (old, old))

    stored = ArxivResolver._write_atomically(tmp_path / "1706.03762.pdf", PDF)

    assert stored.read_bytes() == PDF
    assert not stale.exists()
    assert live.exists()
    assert sorted(path.name for path in tmp_path.iterdir() if path.suffix == ".part") == [live.name]


def test_a_failed_write_still_leaves_no_partial_of_its_own(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(OSError):
        ArxivResolver._write_atomically(tmp_path / "1706.03762.pdf", PDF)

    assert list(tmp_path.glob("*.part")) == []
