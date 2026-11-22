"""A controlled degradation of an analysed paper, to check that the extraction confidence only gets worse as the extraction does (monotone), never better.

`degrade(paper, dimension, severity)` damages a copy of a paper in one measurable way and returns it with the measured damage: "blank_pages" (share of pages with no text), "ocr_noise" (share of
recognised words replaced by noise, scored by the real OCR plausibility measure), "headings_lost" (share of sections dropped) and "paragraphs_merged" (paragraphs joined until the median is very
long). `ladder` scores the confidence level at increasing severity; `monotone` says the level rank never falls. This checks the ORDER of the levels against measurable damage on constructed cases; it
does NOT turn the levels into probabilities, and the thresholds stay reasoned heuristics (extraction_confidence.THRESHOLDS), not calibrated against real papers."""
from copy import deepcopy

SEVERITIES = (0.0, 0.25, 0.5, 0.75, 1.0)
DIMENSIONS = ("blank_pages", "ocr_noise", "headings_lost", "paragraphs_merged")
LEVEL_RANK = {"high": 0, "medium": 1, "low": 2}


def degrade(paper, dimension, severity):
    """(damaged copy, measured damage in 0..1) for one dimension at a severity (0 leaves the paper as it is, 1 destroys that aspect)."""
    damaged = deepcopy(paper)
    if dimension == "blank_pages":
        pages = list(damaged.pages)
        for page in pages[:round(len(pages) * severity)]:
            page.text = ""
        return damaged, sum(1 for p in pages if not p.text.strip()) / max(1, len(pages))
    if dimension == "ocr_noise":
        from backend.ingestion.pdf_ingestion_engine import ocr_quality

        for page in damaged.pages:
            words = page.text.split()
            cut = round(len(words) * severity)
            page.text = " ".join([("xq" + "zk" * (n % 3 + 1)) for n in range(cut)] + words[cut:])
            page.ocr, page.ocr_quality, page.ocr_error = True, round(ocr_quality(page.text), 3), ""
        return damaged, 1 - (sum(p.ocr_quality for p in damaged.pages) / max(1, len(damaged.pages)))
    if dimension == "headings_lost":
        sections = list(damaged.sections)
        keep = len(sections) - round(len(sections) * severity)
        damaged.sections = sections[:keep]
        return damaged, 1 - len(damaged.sections) / max(1, len(sections))
    if dimension == "paragraphs_merged":
        paragraphs, count = list(damaged.paragraphs), round(len(damaged.paragraphs) * severity)
        if count >= 2:
            merged = paragraphs[0]
            merged.content = " ".join(p.content for p in paragraphs[:count])
            damaged.paragraphs = [merged, *paragraphs[count:]]
        return damaged, count / max(1, len(paragraphs))
    raise ValueError(f"unknown dimension {dimension!r}")


def ladder(paper, dimension, assess=None):
    """[{severity, damage, level}] over SEVERITIES for one dimension."""
    from backend.extraction_confidence import assess as default_assess

    rows = []
    for severity in SEVERITIES:
        damaged, damage = degrade(paper, dimension, severity)
        rows.append({"severity": severity, "damage": round(damage, 3), "level": (assess or default_assess)(damaged)["level"]})
    return rows


def monotone(rows):
    """True when the level never improves as the severity rises."""
    ranks = [LEVEL_RANK[row["level"]] for row in rows]
    return all(a <= b for a, b in zip(ranks, ranks[1:]))
