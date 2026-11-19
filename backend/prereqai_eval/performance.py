"""A reproducible performance benchmark: a generated academic PDF of N pages (default 120) through the real pipeline, stage by stage.

`python -m backend.prereqai_eval --performance [--pages 120] [--json]` prints, for a cold run and a repeat of the same file (served by the analysis cache),
the seconds of each pipeline stage, the total, the peak Python memory of the cold run (tracemalloc, MiB) and the process's peak resident size. Timings depend
on the machine: they are for comparing a change on the same machine, never asserted in tests. The text is generated from a fixed template, so the pages'
text is identical on every run (the file's own creation date is not)."""
import resource
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

PARAGRAPH = ("The Transformer relies on self-attention and a softmax over the scores. Gradient descent with the Adam optimizer minimises the cross-entropy loss, "
             "and dropout regularises the network. We use linear algebra and probability throughout, with a policy gradient baseline in the reinforcement learning section. ")


def generate_pdf(path, pages=120):
    """Write a deterministic PDF of `pages` pages: a title, an abstract and numbered sections of body paragraphs, with a short references list at the end."""
    import pymupdf

    document = pymupdf.open()
    for number in range(pages):
        page = document.new_page(width=595, height=842)
        heading = "Abstract" if number == 0 else f"{number} Section {number} Results" if number % 6 == 1 else None
        text = ("Benchmark Paper On Sequence Models\n\n" if number == 0 else "") + (f"{heading}\n\n" if heading else "") + "\n\n".join(PARAGRAPH * 3 for _ in range(4))
        if number == pages - 1:
            text += "\n\nReferences\n\n[1] A. Author. A cited paper. 2017.\n[2] B. Author. Another cited paper. 2018."
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=9)
    document.save(str(path))
    document.close()


def _rss_mib():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


def run_benchmark(pages=120):
    """{"pages", "cold": {"stages", "total_seconds", "peak_python_mib"}, "cached": {...}, "peak_rss_mib"} for the generated PDF; the cache is cleared first."""
    from backend.analysis_cache import analysis_cache
    from backend.platform import platform

    analysis_cache.clear()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "benchmark.pdf"
        generate_pdf(path, pages)
        runs = {}
        for label in ("cold", "cached"):
            tracemalloc.start()
            started = time.perf_counter()
            outcome = platform.analyze(str(path))
            total = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            if outcome["status"] != "success":
                raise RuntimeError(f"the benchmark analysis failed: {outcome.get('detail')}")
            runs[label] = {"stages": {name: round(seconds, 4) for name, seconds in outcome["timings"].items()}, "total_seconds": round(total, 4),
                           "peak_python_mib": round(peak / (1024 * 1024), 1)}
        size = path.stat().st_size
    return {"pages": pages, "pdf_bytes": size, **runs, "peak_rss_mib": _rss_mib()}


def render_performance(report):
    lines = [f"PERFORMANCE ({report['pages']}-page generated PDF, {report['pdf_bytes']} bytes; timings are machine-dependent)"]
    cold = report["cold"]
    lines.append(f"cold run   total {cold['total_seconds']:.3f}s  peak Python memory {cold['peak_python_mib']} MiB")
    for name, seconds in sorted(cold["stages"].items(), key=lambda item: -item[1]):
        lines.append(f"  {name:<28}{seconds:>9.4f}s  {100 * seconds / max(cold['total_seconds'], 1e-9):5.1f}%")
    lines.append(f"cached run total {report['cached']['total_seconds']:.3f}s (the same file again; the pipeline was not rerun)")
    lines.append(f"process peak resident size {report['peak_rss_mib']} MiB")
    return "\n".join(lines)
