"""The CLI summary tells concepts the paper covers itself apart from those the learner marked known."""
from backend.cli import main

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _summary(capsys, *flags):
    assert main(["prerequisites", "analyze", SAMPLE, *flags]) == 0
    return next(line for line in capsys.readouterr().out.splitlines() if line.strip().startswith("concepts:"))


def test_known_concepts_are_not_reported_as_covered_in_the_paper(capsys):
    line = _summary(capsys, "--known", "Linear Algebra,Probability,Calculus,Neural Networks")
    assert line.endswith("missing: 0 (1 covered in the paper, 4 marked known)")
    assert "5 covered in the paper" not in line


def test_summary_without_known_is_unchanged(capsys):
    assert _summary(capsys).endswith("missing: 4 (1 covered in the paper)")


def test_only_known_concepts_are_described_as_known(capsys):
    assert _summary(capsys, "--known", "Calculus").endswith("missing: 3 (1 covered in the paper, 1 marked known)")
