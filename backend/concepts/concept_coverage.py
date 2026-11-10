def concept_detection_coverage(registered, detected):
    """Document-level detection coverage: how many of the registry's concepts were found in this document.

    This says nothing about concepts the registry does not know, and it is not the share of the paper that is understood.
    The ratio is 0.0 when the registry is empty."""
    registered, detected = int(registered), int(detected)
    return {
        "registered_concepts": registered,
        "detected_concepts": detected,
        "detection_coverage_ratio": round(detected / registered, 4) if registered > 0 else 0.0,
    }
