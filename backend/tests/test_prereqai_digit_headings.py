"""A numbered heading may name a dataset, model or size ("4 Experiments on CIFAR-10", "5.2 Results on GPT-4"); table rows of figures and sentences are still body text."""
from types import SimpleNamespace

import pytest

from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser
from backend.prereqai_eval import pdf_eval

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("heading", ["4 Experiments on CIFAR-10", "5.2 Results on GPT-4", "3 Scaling to 7B Models", "2 ImageNet-1k Pretraining", "4.3 Training on 8B Tokens", "7 BERT-Large Results", "3 GPT-4 Evaluation", "4 Experiments on MNIST"])
def test_numbered_headings_that_name_a_dataset_or_model_are_recognised(heading):
    assert SECTION_PATTERN.search(heading)


@pytest.mark.parametrize("line", [
    "1 Baseline 12 34 56",
    "2 Model 0.5 1.2 3.4",
    "3 7 8 9",
    "4 Accuracy 91 92 93 94",
    "4 We evaluate on CIFAR-10.",
    "5.2 Results on GPT-4 are shown in Table 2.",
    "3 NVIDIA A100 GPUs were used, 80 GB each, for all runs and for the ablations",
])
def test_figures_rows_and_sentences_stay_body_text(line):
    assert SECTION_PATTERN.search(line) is None


def test_a_bare_number_inside_a_title_is_still_not_a_title_word():
    assert SECTION_PATTERN.search("6.1 Llama 2 Evaluation") is None  # known limitation: "Llama 2" cannot be told from a table row such as "1 Baseline 2 Ours" by the line alone


def test_existing_numbered_and_unnumbered_headings_are_unchanged():
    for heading in ("3.2 Scaled Dot-Product Attention", "1 Introduction", "II. Proposed Method", "Related Work", "A Proofs"):
        assert SECTION_PATTERN.search(heading) or heading == "A Proofs"  # lettered appendices are trusted only after the references heading


def test_a_document_splits_at_the_digit_headings_and_keeps_their_text():
    text = ("1 Introduction\nWe study image models.\n4 Experiments on CIFAR-10\nAccuracy is 94.1.\n5.2 Results on GPT-4\nIt works.\n"
            "1 Baseline 12 34 56\n2 Model 0.5 1.2\nReferences\n[1] Policy gradient methods.\n")
    paper = ScientificSectionParser().parse(SimpleNamespace(source_path="p.pdf", metadata=None, pages=[], full_text=text))
    assert [section.title for section in paper.sections] == ["1 Introduction", "4 Experiments on CIFAR-10", "5.2 Results on GPT-4", "References"]
    assert "Accuracy is 94.1." in paper.sections[1].content and "1 Baseline 12 34 56" in paper.sections[2].content


def test_the_synthetic_pdf_that_recorded_the_miss_now_finds_the_heading_and_loses_none():
    report = pdf_eval.evaluate_pdf()
    numbered = next(item for item in report["fixtures"] if item["id"] == "numbered-1col")
    assert numbered["headings"]["missed"] == [] and numbered["headings"]["spurious"] == [] and report["headings"]["recall"] == 1.0 and report["headings"]["precision"] == 1.0
