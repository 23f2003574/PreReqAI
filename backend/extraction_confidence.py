"""How far the extraction of one paper can be trusted, and what the learner can do about it.

Seven signals are measured from the analysed paper (text layer, OCR, headings, references, citations, paragraph layout, concepts); each is "ok", "warn" or "poor" with a measured value, and each
that is not ok has a plain warning with an action. The overall level is "low" when any signal is poor, "medium" when any is a warning, else "high". Nothing is hidden by a low level: the report
still lists everything found, with the level and warnings beside it, so the learner knows which results to double-check. Thresholds are in THRESHOLDS; they are reading aids, not probabilities."""
from statistics import median

THRESHOLDS = {"text_pages_ok": 0.9, "text_pages_poor": 0.5, "page_chars": 20, "ocr_quality_ok": 0.75, "ocr_quality_poor": 0.4, "headings_min": 3, "citations_unresolved_warn": 0.3, "paragraph_chars_warn": 2500}


def _signal(name, status, value, detail, action=""):
    return {"name": name, "status": status, "value": value, "detail": detail, "action": action}


def _text_layer(paper):
    pages = list(getattr(paper, "pages", []) or [])
    if not pages:
        return _signal("text_layer", "poor", 0.0, "No page text was read.", "Check that the file is a readable PDF and upload it again.")
    readable = sum(1 for p in pages if len((p.text or "").strip()) >= THRESHOLDS["page_chars"]) / len(pages)
    if readable < THRESHOLDS["text_pages_poor"]:
        return _signal("text_layer", "poor", round(readable, 2), f"Only {readable:.0%} of the pages have any readable text (a scan, or mostly figures).", "Use a text-based PDF, or the original source if you have it.")
    if readable < THRESHOLDS["text_pages_ok"]:
        return _signal("text_layer", "warn", round(readable, 2), f"{1 - readable:.0%} of the pages have almost no readable text (figures, scans or blank pages).", "Check that nothing you need is on those pages.")
    return _signal("text_layer", "ok", round(readable, 2), "Every page has text.")


def _ocr(paper):
    pages = [p for p in getattr(paper, "pages", []) or [] if getattr(p, "ocr", False) or getattr(p, "ocr_error", "")]
    if not pages:
        return _signal("ocr", "ok", None, "No page needed OCR.")
    failed = [p for p in pages if p.ocr_error]
    stopped = [p for p in pages if getattr(p, "ocr_stopped", False)]
    qualities = [p.ocr_quality for p in pages if p.ocr and p.ocr_quality is not None]
    if failed and not qualities:
        return _signal("ocr", "poor", 0.0, f"{len(failed)} scanned page{'s' if len(failed) != 1 else ''} could not be read: {failed[0].ocr_error}", "Use a clearer scan, or a text-based PDF.")
    mean = round(sum(qualities) / len(qualities), 2) if qualities else None
    if stopped:
        return _signal("ocr", "warn", mean, f"OCR stopped before {len(stopped)} page{'s' if len(stopped) != 1 else ''} were read, so the analysis is partial.", "Raise the OCR limits or analyse a smaller part of the paper.")
    if mean is not None and mean < THRESHOLDS["ocr_quality_poor"]:  # found by the controlled degradation (confidence_eval.py): text this noisy stayed at "medium" before
        return _signal("ocr", "poor", mean, f"Recognised text scores only {mean} of 1: most words are probably wrong.", "Use a clearer scan, or a text-based PDF.")
    if failed or (mean is not None and mean < THRESHOLDS["ocr_quality_ok"]):
        return _signal("ocr", "warn", mean, f"{len(failed)} scanned page(s) were left unread and the recognised text scores {mean} of 1." if failed else f"Recognised text scores {mean} of 1: some words may be wrong.",
                       "Check the quoted evidence against the page, or use a text-based PDF.")
    return _signal("ocr", "ok", mean, f"{len(qualities)} scanned page(s) were read with a text-quality score of {mean} of 1.")


def _headings(paper):
    sections = [s for s in getattr(paper, "sections", []) or [] if s.title != "Front Matter"]
    titles = [s.title for s in sections]
    if not sections:
        return _signal("headings", "poor", 0, "No section headings were recognised, so the paper's structure (and which sections teach and which cite) is unknown.", "Treat section-based results with care; check the page numbers.")
    repeated = sorted({t for t in titles if titles.count(t) > 1})
    if len(sections) < THRESHOLDS["headings_min"] or repeated:
        why = f"only {len(sections)} heading{'s' if len(sections) != 1 else ''} were found" if len(sections) < THRESHOLDS["headings_min"] else f"the heading {repeated[0]!r} appears more than once"
        return _signal("headings", "warn", len(sections), f"The structure may be incomplete: {why}.", "Check the section names beside each piece of evidence.")
    return _signal("headings", "ok", len(sections), f"{len(sections)} section headings were recognised.")


def _references(paper):
    count = len([r for r in getattr(paper, "references", []) or [] if (r.raw_text or "").strip()])
    if not count:
        return _signal("references", "warn", 0, "No bibliography entries were extracted, so cited works and the reading list are unavailable.", "Check whether the PDF includes its reference list.")
    return _signal("references", "ok", count, f"{count} bibliography entries were extracted.")


def _citations(paper):
    citations = list(getattr(paper, "citations", []) or [])
    known = {r.reference_number for r in getattr(paper, "references", []) or []}
    if not citations:
        return _signal("citations", "ok", None, "No in-text citations were linked (nothing to resolve).")
    unresolved = sum(1 for c in citations if c.reference_number not in known) / len(citations)
    if unresolved > THRESHOLDS["citations_unresolved_warn"]:
        return _signal("citations", "warn", round(1 - unresolved, 2), f"{unresolved:.0%} of the in-text citations do not match a bibliography entry.", "The reading list may miss works the paper cites.")
    return _signal("citations", "ok", round(1 - unresolved, 2), "In-text citations match the bibliography.")


def _layout(paper):
    paragraphs = list(getattr(paper, "paragraphs", []) or [])
    if not paragraphs:
        return _signal("layout", "poor", 0, "No paragraphs were reconstructed from the layout.", "Quoted evidence may be missing; check the paper's own text.")
    middle = median(len(p.content or "") for p in paragraphs)
    if middle > THRESHOLDS["paragraph_chars_warn"]:
        return _signal("layout", "warn", round(middle), f"Paragraphs are very long (median {middle:.0f} characters): their boundaries were probably not recovered (columns, footnotes or a scan).", "Evidence sentences may mix neighbouring text; check the page.")
    return _signal("layout", "ok", round(middle), f"Paragraphs were reconstructed (median {middle:.0f} characters).")


def _concepts(paper):
    count = len(getattr(paper, "concepts", []) or [])
    if not count:
        return _signal("concepts", "warn", 0, "No concept PreReqAI knows was detected, so there are no prerequisite recommendations.", "The paper may be outside machine learning; see the candidate terms and confirm the ones you need.")
    return _signal("concepts", "ok", count, f"{count} known concepts were detected.")


def assess(paper):
    """{"level": "high"|"medium"|"low", "signals": [...], "warnings": [{signal, severity, message, action}], "note": str}."""
    signals = [_text_layer(paper), _ocr(paper), _headings(paper), _references(paper), _citations(paper), _layout(paper), _concepts(paper)]
    bad = [s for s in signals if s["status"] != "ok"]
    level = "low" if any(s["status"] == "poor" for s in signals) else "medium" if bad else "high"
    warnings = [{"signal": s["name"], "severity": s["status"], "message": s["detail"], "action": s["action"]} for s in bad]
    note = {"high": "No extraction problem was found.", "medium": "Some parts of the extraction may be incomplete; the warnings say which.",
            "low": "The extraction is unreliable in at least one important way: check the results against the paper before relying on them."}[level]
    return {"level": level, "signals": signals, "warnings": warnings, "note": note}


def warning_lines(confidence):
    """The lines worth adding to a run's warnings: only a poor text layer or OCR (the text itself is unreliable), so a normal paper adds nothing; structure signals (headings, layout) are
    reported in the report and on the page, where a paper without headings is a normal case."""
    return [f"Extraction confidence is low: {w['message']} {w['action']}".strip() for w in confidence["warnings"] if w["severity"] == "poor" and w["signal"] in ("text_layer", "ocr")]


# What each signal means for the results built on it. Text and OCR problems make every detected concept, and so every prerequisite and plan step derived from them, doubtful; heading and
# paragraph-layout problems make the quoted evidence and section-based importance doubtful; references and citations only affect the reading list. These are reading aids, NOT calibrated
# probabilities: the thresholds were chosen by reasoning and are only checked for being monotone on controlled degradations (prereqai_eval/confidence_eval.py).
STAGE = {"text_layer": "the PDF's text layer", "ocr": "OCR of scanned pages", "headings": "section heading detection", "references": "the reference list", "citations": "citation linking",
         "layout": "paragraph layout recovery", "concepts": "concept detection"}
DOUBTS_CONCEPTS = ("text_layer", "ocr", "concepts")
DOUBTS_EVIDENCE = ("headings", "layout")
RANK = {"ok": 0, "warn": 1, "poor": 2}


def effects(confidence):
    """{"level", "guard_adaptation", "concepts": [reasons], "evidence": [reasons], "note"}: `concepts` are the not-ok signals that put every concept-derived result in doubt, `evidence` those that put
    quoted evidence and section-based importance in doubt (each {signal, stage, severity, message}). The adaptation guard is on when the text itself is unreliable (a poor text layer or poor OCR):
    a plan must not be changed on its own from results the extraction makes unreliable, until the learner confirms it. Weak structure alone (few headings) does not switch it on."""
    signals = {s["name"]: s for s in confidence.get("signals", [])}
    make = lambda names: [{"signal": n, "stage": STAGE[n], "severity": signals[n]["status"], "message": signals[n]["detail"]} for n in names if n in signals and signals[n]["status"] != "ok"]
    return {"level": confidence.get("level"), "guard_adaptation": any(signals.get(name, {}).get("status") == "poor" for name in ("text_layer", "ocr")), "concepts": make(DOUBTS_CONCEPTS), "evidence": make(DOUBTS_EVIDENCE),
            "note": "Results marked unreliable rest on a part of the extraction that failed; check them against the paper." if confidence.get("level") in ("medium", "low") else ""}


def _flag(reasons):
    worst = max(reasons, key=lambda r: RANK[r["severity"]])
    return {"level": "low" if worst["severity"] == "poor" else "medium", "stage": worst["stage"], "message": worst["message"], "stages": sorted({r["stage"] for r in reasons})}


def propagate(report):
    """The report with `confidence_effects` and a `confidence_flag` on every prerequisite, plan step and math step that rests on a doubtful stage (None when nothing does). Nothing is removed or
    reworded: the learner sees the result and why it is in doubt. A report without extraction confidence (saved before it existed) is returned unchanged."""
    confidence = report.get("extraction_confidence")
    if not confidence:
        return report
    found = effects(confidence)
    report["confidence_effects"] = found
    flag = _flag(found["concepts"]) if found["concepts"] else None
    evidence_flag = _flag(found["evidence"]) if found["evidence"] else None
    for prerequisite in report.get("prerequisites", []):
        prerequisite["confidence_flag"] = flag or (evidence_flag if prerequisite.get("evidence") else None)
    flagged = {p["concept"]: p["confidence_flag"] for p in report.get("prerequisites", [])}
    for step in [*report.get("learning_plan", []), *report.get("math_plan", [])]:
        step["confidence_flag"] = flagged.get(step["concept"]) or flag
    return report
