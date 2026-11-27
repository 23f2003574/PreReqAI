"""Negative controls: short documents from other fields that use words PreReqAI's registry also knows ("transformer", "dropout", "attention", "regularization", "embedding"). A paper that says nothing about
machine learning must produce no machine-learning concept and no machine-learning prerequisite; each control is a generated PDF run through the production pipeline. They are hand-written (AI-authored,
provisional) and few: they guard against a regression of the domain rule, they do not measure how well it generalises to real non-ML papers."""
import os
import tempfile

CONTROLS = {
    "power-grid": ["Transformer Faults in Power Grids", "1 Introduction",
                   "Power transformer faults in substations are costly. The transformer winding overheats and the transformer oil degrades.",
                   "A transformer with high load fails early. The residual stress of the tank is low.",
                   "Regularization of the grid by the state is discussed. The transformer is inspected yearly.",
                   "2 Method", "We measure transformer temperature with sensors and compare transformer ratings across substations."],
    "student-dropout": ["Student Dropout in Universities", "1 Introduction",
                        "Student dropout in universities is rising. Dropout rates rose after the pandemic.",
                        "Dropout is highest in the first year. Attention to students matters, and attention from teachers.",
                        "The embedding of students in the community helps. Overfitting of curricula to exams is a concern.",
                        "2 Method", "We survey dropout across departments and relate dropout to attention from advisers."],
}


def _pdf(lines):
    import pymupdf  # a runtime requirement, unlike reportlab

    handle, path = tempfile.mkstemp(suffix=".pdf")
    os.close(handle)
    document = pymupdf.open()
    page, y = document.new_page(), 52
    for line in lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 16
    document.save(path)
    document.close()
    return path


def evaluate(controls=None):
    """{"controls": {name: {"concepts": [...], "prerequisites": [...]}}, "clean": share of controls with neither}."""
    from backend.pipeline import ResearchPaperPipeline

    found = {}
    for name, lines in (controls or CONTROLS).items():
        path = _pdf(lines)
        try:
            paper = ResearchPaperPipeline().run(path).paper
        finally:
            os.remove(path)
        found[name] = {"concepts": [c.name for c in paper.concepts], "prerequisites": [p.concept for p in paper.prerequisites]}
    clean = sum(1 for row in found.values() if not row["concepts"] and not row["prerequisites"])
    return {"controls": found, "clean": clean / len(found) if found else 1.0}
