from types import SimpleNamespace as N

import pymupdf

from backend.platform import platform
from backend.reporting import LearningReportGenerator


def _paper(sections, equations, concepts):
    return N(
        sections=[N(title=t, content=c) for t, c in sections],
        equations=[N(equation_id=i, expression=e, section=s) for i, (s, e) in enumerate(equations, 1)],
        concepts=[N(name=c) for c in concepts],
    )


def test_each_equation_lists_the_concepts_discussed_just_before_it():
    paper = _paper(
        [("Method", "x" * 400 + "\nGradient Descent updates the weights.\nw = w - lr * g\nSoftmax is used here\np = softmax(z)\n")],
        [("Method", "w = w - lr * g"), ("Method", "p = softmax(z)")],
        ["Gradient Descent", "Softmax", "Dropout"],
    )
    equations = LearningReportGenerator._equations(paper)
    assert [e["id"] for e in equations] == [1, 2]
    assert equations[0]["concepts"] == ["Gradient Descent"]  # Softmax comes after it
    assert equations[1]["concepts"] == ["Gradient Descent", "Softmax"] and "Dropout" not in equations[1]["concepts"]


def test_no_equations_and_unknown_section_are_handled():
    assert LearningReportGenerator._equations(_paper([("A", "text")], [], ["Softmax"])) == []
    only = LearningReportGenerator._equations(_paper([("A", "Softmax")], [("Missing", "a = b")], ["Softmax"]))
    assert only[0]["concepts"] == []


def test_analysis_report_carries_the_equation_map(tmp_path):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 60), "Method", fontsize=16)
    page.insert_textbox((50, 90, 550, 300), "Attention weights come from Softmax.\nA = softmax(QK^T)\n", fontsize=10)
    path = tmp_path / "eq.pdf"
    document.save(str(path))
    report = platform.analyze(str(path))["report"]
    assert report["statistics"]["equations"] == len(report["equations"]) == 1
    assert report["equations"][0]["expression"] == "A = softmax(QK^T)"
    assert {"Attention", "Softmax"} <= set(report["equations"][0]["concepts"])
